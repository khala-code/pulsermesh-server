"""
app/services/gossip.py — Gossip layer (Mode A: direct HTTP, v1)

This module handles three concerns:

  1. NodeGossip assembly
     Build the local NodeGossip payload from current checkpoint + node
     PLL state.  Pure computation — no I/O.

  2. Inbound receipt processing
     Validate an inbound NodeGossip, compute Q_cross, detect sign-flip,
     write a GossipLog entry.  Pure DB write — no HTTP.

  3. Outbound emit loop
     Called by checkpoint.advance_checkpoint() after each advance.
     Iterates the peers table, POSTs to every peer URL, updates
     peers.last_seen_* on success, logs every attempt.

v2 seam
-------
GossipEnvelope (relay metadata, broker consistency check) and
steward-mediated peer discovery are v2 additions.  They plug into the
POST /gossip endpoint as an extended request body without breaking the
v1 NodeGossip path.  This module exposes process_inbound() which the
router calls; the router is responsible for unpacking the envelope in v2.

Design constraint: this module must never import from app.routers.*.
"""
import logging
import math
from datetime import datetime, UTC
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models.peer import Peer
from app.models.gossip_log import GossipLog
from app.schemas.gossip import NodeGossip
from app.services.asymptotic import (
    node_quadrature_aggregate,
    order_parameter,
    phase_lag_signal,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sign-flip detection threshold
# A Q_cross sign change is only meaningful if the magnitude is above noise.
# Below this threshold the PLL signal is effectively zero and sign is
# uninformative.  Tunable via env in v2; hardcoded for v1.
# ---------------------------------------------------------------------------
SIGN_FLIP_MAGNITUDE_THRESHOLD = 0.05

# ---------------------------------------------------------------------------
# HTTP client timeout for outbound gossip POST
# ---------------------------------------------------------------------------
GOSSIP_HTTP_TIMEOUT = 5.0  # seconds


# ===========================================================================
# 1. NodeGossip assembly
# ===========================================================================

def assemble_node_gossip(
    checkpoint_index: int,
    checkpoint_hash: str,
    ta_ref: float,
    steward_positions: list[tuple[float, float]],  # [(oa, za), ...]
) -> NodeGossip:
    """
    Build the NodeGossip payload this node will POST to its peers.

    Parameters
    ----------
    checkpoint_index
        The index of the checkpoint just advanced.
    checkpoint_hash
        The structural hash of that checkpoint.
    ta_ref
        The Ta reference agreed at this checkpoint.
    steward_positions
        Snapshot of all active steward (oa, za) pairs at the time of
        this checkpoint advance.  Used to compute Q_cross and Phi.

    Returns
    -------
    NodeGossip
        Ready to serialise and POST to peers.
    """
    za_node = settings.node_za
    omega_a = settings.node_oa

    q_cross = node_quadrature_aggregate(steward_positions, za_node)
    phi = order_parameter(steward_positions) if steward_positions else 0.0

    return NodeGossip(
        node_id=settings.node_id,
        checkpoint_index=checkpoint_index,
        checkpoint_hash=checkpoint_hash,
        za=za_node,
        omega_a=omega_a,
        q_cross=q_cross,
        phi=phi,
        ta_ref=ta_ref,
    )


# ===========================================================================
# 2. Inbound receipt processing
# ===========================================================================

def _detect_sign_flip(
    q_cross_new: float,
    peer_id: str,
    db: Session,
) -> bool:
    """
    Return True if q_cross_new has flipped sign relative to the most
    recent inbound log entry for this peer, and both magnitudes exceed
    SIGN_FLIP_MAGNITUDE_THRESHOLD.

    A single sign flip may be normal network jitter.  The gossip service
    sets anomaly_flagged=True on the log entry; it is the operator's
    (and future automated policy's) job to decide what to do with it.
    """
    if abs(q_cross_new) < SIGN_FLIP_MAGNITUDE_THRESHOLD:
        return False

    prev = (
        db.query(GossipLog)
        .filter(
            GossipLog.peer_id == peer_id,
            GossipLog.direction == "inbound",
            GossipLog.q_cross.isnot(None),
        )
        .order_by(GossipLog.id.desc())
        .first()
    )
    if prev is None or prev.q_cross is None:
        return False
    if abs(prev.q_cross) < SIGN_FLIP_MAGNITUDE_THRESHOLD:
        return False

    return math.copysign(1.0, q_cross_new) != math.copysign(1.0, prev.q_cross)


def process_inbound(
    payload: NodeGossip,
    db: Session,
) -> GossipLog:
    """
    Process an inbound NodeGossip from a peer.

    Steps
    -----
    1. Compute Q_cross from the sender's Za against our node Za.
       Note: the sender already computed their own Q_cross against their
       steward population.  We recompute Q_cross from *their* Za against
       *our* node Za so we have a local reference signal.
    2. Detect sign-flip relative to the last inbound entry for this peer.
    3. Write an immutable GossipLog row.
    4. Return the log entry (router may use it for the response body).

    This function does NOT update peers.last_seen_* — that is done by
    the router on a successful inbound receipt (HTTP 200 response path).
    """
    q_cross_local = phase_lag_signal(
        oa=payload.omega_a,
        za_steward=payload.za,
        za_node=settings.node_za,
    )
    sign_flip = _detect_sign_flip(q_cross_local, payload.node_id, db)

    entry = GossipLog(
        direction="inbound",
        peer_id=payload.node_id,
        checkpoint_index=payload.checkpoint_index,
        delivered=True,
        q_cross=q_cross_local,
        sign_flip=sign_flip,
        anomaly_flagged=sign_flip,  # initial flag; operator may amend in v2
        raw_node_id=payload.node_id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    if sign_flip:
        log.warning(
            "gossip sign-flip detected: peer=%s checkpoint=%d "
            "q_cross_prev→new=%.4f (flagged)",
            payload.node_id,
            payload.checkpoint_index,
            q_cross_local,
        )
    else:
        log.debug(
            "gossip inbound: peer=%s checkpoint=%d q_cross=%.4f phi=%.4f",
            payload.node_id,
            payload.checkpoint_index,
            q_cross_local,
            payload.phi,
        )

    return entry


# ===========================================================================
# 3. Outbound emit loop
# ===========================================================================

def emit_gossip(
    db: Session,
    checkpoint_index: int,
    checkpoint_hash: str,
    ta_ref: float,
    steward_positions: list[tuple[float, float]],
) -> None:
    """
    Assemble a NodeGossip and POST it to every peer in the peers table.

    Called by checkpoint.advance_checkpoint() after committing the new
    checkpoint row.  Failures are logged and never raise — a gossip
    delivery failure must never prevent the checkpoint from advancing.

    For each peer:
      - On success (HTTP 2xx): update last_seen_checkpoint / last_seen_at,
        write outbound GossipLog(delivered=True).
      - On failure (non-2xx or network error): write
        outbound GossipLog(delivered=False).  peers.last_seen_* unchanged.
    """
    peers = db.query(Peer).all()
    if not peers:
        log.debug("gossip emit: no peers registered, skipping")
        return

    gossip = assemble_node_gossip(
        checkpoint_index=checkpoint_index,
        checkpoint_hash=checkpoint_hash,
        ta_ref=ta_ref,
        steward_positions=steward_positions,
    )
    payload = gossip.model_dump()

    for peer in peers:
        _deliver_to_peer(db, peer, payload, checkpoint_index)


def _deliver_to_peer(
    db: Session,
    peer: Peer,
    payload: dict,
    checkpoint_index: int,
) -> None:
    """Attempt delivery to a single peer; write a GossipLog entry either way."""
    delivered = False
    try:
        resp = httpx.post(
            f"{peer.url.rstrip('/')}/gossip",
            json=payload,
            timeout=GOSSIP_HTTP_TIMEOUT,
        )
        delivered = resp.is_success
        if not delivered:
            log.warning(
                "gossip emit: peer=%s checkpoint=%d HTTP %d",
                peer.peer_id, checkpoint_index, resp.status_code,
            )
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "gossip emit: peer=%s checkpoint=%d network error: %s",
            peer.peer_id, checkpoint_index, exc,
        )

    # Write log entry
    entry = GossipLog(
        direction="outbound",
        peer_id=peer.peer_id,
        checkpoint_index=checkpoint_index,
        delivered=delivered,
    )
    db.add(entry)

    # Update last_seen on success
    if delivered:
        peer.last_seen_checkpoint = checkpoint_index
        peer.last_seen_at = datetime.now(UTC)

    try:
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        log.error(
            "gossip emit: DB commit failed for peer=%s: %s",
            peer.peer_id, exc,
        )
