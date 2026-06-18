"""
app/routers/gossip.py — Gossip HTTP endpoints (Mode A, v1)

Endpoints
---------
POST /gossip
    Receive a NodeGossip payload from a peer.
    No auth — any node on the mesh can deliver.  The payload is validated
    by Pydantic (NodeGossip schema); process_inbound() handles the logic.
    On success, updates peers.last_seen_* if the sender is a known peer.
    Returns the GossipLog entry for observability.

GET  /gossip/peers
    List all registered peers with last_seen state.  Admin-auth.

POST /gossip/peers
    Register a new peer by {peer_id, url}.  Admin-auth.
    409 if peer_id already exists.

DELETE /gossip/peers/{peer_id}
    Remove a peer.  Admin-auth.  404 if not found.

v2 seam
-------
GossipEnvelope unpacking (relay metadata, broker consistency check) will
be added here as an optional outer body field.  The NodeGossip inner
payload path is unchanged.
"""
import logging
from datetime import datetime, UTC

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.database import get_db
from app.models.peer import Peer
from app.schemas.gossip import NodeGossip, PeerCreate, PeerRead, GossipLogRead
from app.services.gossip import process_inbound

log = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# POST /gossip  — receive inbound gossip (no auth)
# ---------------------------------------------------------------------------

@router.post("", status_code=status.HTTP_200_OK)
def receive_gossip(
    payload: NodeGossip,
    db: Session = Depends(get_db),
) -> GossipLogRead:
    """
    Accept a NodeGossip from any peer.

    Processing:
    1. Delegate to gossip.process_inbound() — computes q_cross_local,
       detects sign-flip, writes an immutable GossipLog row.
    2. If the sender is a registered peer, update last_seen_checkpoint
       and last_seen_at.
    3. Return the GossipLog entry so the sender gets observability
       feedback (their Q_cross as seen from our Za reference).
    """
    entry = process_inbound(payload, db)

    # Update last_seen if this node is a registered peer
    peer = db.query(Peer).filter_by(peer_id=payload.node_id).first()
    if peer:
        peer.last_seen_checkpoint = payload.checkpoint_index
        peer.last_seen_at = datetime.now(UTC)
        db.commit()
        log.debug(
            "gossip inbound: updated last_seen for registered peer=%s checkpoint=%d",
            payload.node_id, payload.checkpoint_index,
        )
    else:
        log.debug(
            "gossip inbound: sender peer_id=%s is not a registered peer (unregistered node)",
            payload.node_id,
        )

    return GossipLogRead.model_validate(entry)


# ---------------------------------------------------------------------------
# GET /gossip/peers  — list peers (admin)
# ---------------------------------------------------------------------------

@router.get("/peers", status_code=status.HTTP_200_OK)
def list_peers(
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
) -> list[PeerRead]:
    """Return all registered peers with last_seen state."""
    peers = db.query(Peer).order_by(Peer.added_at).all()
    return [PeerRead.model_validate(p) for p in peers]


# ---------------------------------------------------------------------------
# POST /gossip/peers  — add peer (admin)
# ---------------------------------------------------------------------------

@router.post("/peers", status_code=status.HTTP_201_CREATED)
def add_peer(
    body: PeerCreate,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
) -> PeerRead:
    """
    Register a new peer by {peer_id, url}.

    409 Conflict if peer_id already exists.
    """
    existing = db.query(Peer).filter_by(peer_id=body.peer_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Peer '{body.peer_id}' is already registered",
        )
    peer = Peer(peer_id=body.peer_id, url=body.url)
    db.add(peer)
    db.commit()
    db.refresh(peer)
    log.info("gossip peer registered: peer_id=%s url=%s", peer.peer_id, peer.url)
    return PeerRead.model_validate(peer)


# ---------------------------------------------------------------------------
# DELETE /gossip/peers/{peer_id}  — remove peer (admin)
# ---------------------------------------------------------------------------

@router.delete("/peers/{peer_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_peer(
    peer_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
) -> None:
    """
    Deregister a peer.  404 if not found.

    GossipLog rows for this peer are retained (append-only log).
    """
    peer = db.query(Peer).filter_by(peer_id=peer_id).first()
    if not peer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Peer '{peer_id}' not found",
        )
    db.delete(peer)
    db.commit()
    log.info("gossip peer removed: peer_id=%s", peer_id)
