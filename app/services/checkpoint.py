import logging
from datetime import datetime, UTC
from sqlalchemy.orm import Session
from app.models.checkpoint import Checkpoint
from app.models.identity import OaZaTaIdentity
from app.config import settings
from app.services.crypto import digest, keyed_digest

log = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64


def get_current_checkpoint(db: Session) -> Checkpoint:
    cp = db.query(Checkpoint).order_by(Checkpoint.index.desc()).first()
    if not cp:
        cp = _create_genesis(db)
    return cp


def advance_checkpoint(db: Session, ta_ref: float) -> Checkpoint:
    """
    Advance the mesh clock by one checkpoint.

    After committing the new Checkpoint row:
      1. Runs snark.update_snark_identity() for every steward that has an
         OaZaTaIdentity. Snark failures are logged and skipped.
      2. Runs gossip.emit_gossip() to broadcast the new checkpoint to all
         registered peers. Gossip failures are logged and skipped.

    Neither post-commit step can prevent the checkpoint from advancing.
    Both use deferred imports to prevent circular dependencies.
    """
    current = get_current_checkpoint(db)
    new_index = current.index + 1
    new_hash = _derive_checkpoint_hash(
        index=new_index,
        node_id=settings.node_id,
        prev_hash=current.hash,
        ta_ref=ta_ref
    )
    cp = Checkpoint(
        index=new_index,
        hash=new_hash,
        ta_ref=ta_ref,
        prev_hash=current.hash,
        advanced_at=datetime.now(UTC)
    )
    db.add(cp)
    db.commit()
    db.refresh(cp)

    _run_snark_updates(db)
    _run_gossip_emit(db, cp)

    return cp


def _run_snark_updates(db: Session) -> None:
    """
    Recompute snark fields for every steward with an identity.

    Imported inside the function to avoid a circular import:
    snark → asymptotic → (no further deps), but if checkpoint were
    imported at module level by snark in the future, it would cycle.
    """
    from app.services import snark  # deferred import

    identities = db.query(OaZaTaIdentity).all()
    for identity in identities:
        try:
            update = snark.update_snark_identity(
                db=db,
                steward_id=identity.steward_id,
                identity=identity,
            )
            log.debug(
                "snark updated steward=%s pulse_count=%d "
                "null_centroid_za=%s mission_delta=%s uncertainty_radius=%.4f",
                update.steward_id,
                update.pulse_count,
                f"{update.null_centroid_za:.4f}" if update.null_centroid_za is not None else "None",
                f"{update.mission_delta:.4f}" if update.mission_delta is not None else "None",
                update.uncertainty_radius,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "snark update failed for steward=%s: %s",
                identity.steward_id, exc,
            )


def _run_gossip_emit(db: Session, cp: Checkpoint) -> None:
    """
    Broadcast the new checkpoint to all registered peers via gossip.

    Steward (oa, za) pairs are snapshotted from OaZaTaIdentity at the
    moment of the checkpoint advance — this is the same population the
    snark step just updated, so the positions are fresh.

    Deferred import mirrors _run_snark_updates to prevent any future
    circular dependency if gossip ever imports from checkpoint.

    Gossip delivery failures are swallowed here — emit_gossip() itself
    never raises, but we guard with try/except anyway for belt-and-braces.
    """
    from app.services.gossip import emit_gossip  # deferred import

    try:
        identities = db.query(OaZaTaIdentity).all()
        steward_positions = [(i.oa, i.za) for i in identities]

        emit_gossip(
            db=db,
            checkpoint_index=cp.index,
            checkpoint_hash=cp.hash,
            ta_ref=cp.ta_ref,
            steward_positions=steward_positions,
        )
        log.debug(
            "gossip emitted: checkpoint=%d peers=%d stewards=%d",
            cp.index,
            db.query(__import__('app.models.peer', fromlist=['Peer']).Peer).count(),
            len(steward_positions),
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("gossip emit failed at checkpoint=%d: %s", cp.index, exc)


def derive_steward_key(steward_id: str, oa: float, za: float, ta: float, checkpoint_hash: str) -> str:
    """
    Derive a steward's pm_ key from their rotor phase + checkpoint hash.

    Routed through crypto.keyed_digest so the underlying primitive is
    swappable without touching this call site.
    See docs/architecture.md § Principle 7.
    """
    raw = f"{steward_id}|{oa}|{za}|{ta}|{checkpoint_hash}"
    h = keyed_digest(raw, settings.api_key_secret)
    return f"pm_{h}"


def get_valid_keys_for_steward(
    steward_id: str,
    oa: float,
    za: float,
    ta: float,
    db: Session,
    grace_window: int = 2
) -> list[str]:
    checkpoints = (
        db.query(Checkpoint)
        .order_by(Checkpoint.index.desc())
        .limit(grace_window + 1)
        .all()
    )
    return [
        derive_steward_key(steward_id, oa, za, ta, cp.hash)
        for cp in checkpoints
    ]


def _create_genesis(db: Session) -> Checkpoint:
    genesis_hash = _derive_checkpoint_hash(
        index=0,
        node_id=settings.node_id,
        prev_hash=GENESIS_HASH,
        ta_ref=0.0
    )
    cp = Checkpoint(
        index=0,
        hash=genesis_hash,
        ta_ref=0.0,
        prev_hash=None,
        advanced_at=datetime.now(UTC)
    )
    db.add(cp)
    db.commit()
    db.refresh(cp)
    return cp


def _derive_checkpoint_hash(index: int, node_id: str, prev_hash: str, ta_ref: float) -> str:
    """
    Structural hash of a checkpoint.

    Routed through crypto.digest so the primitive is swappable.
    See docs/architecture.md § Principle 7.
    """
    raw = f"{index}|{node_id}|{prev_hash}|{ta_ref}"
    return digest(raw)
