import hashlib
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.checkpoint import Checkpoint
from app.config import settings


GENESIS_HASH = "0" * 64


def get_current_checkpoint(db: Session) -> Checkpoint:
    """Return the latest checkpoint. Creates genesis if none exists."""
    cp = db.query(Checkpoint).order_by(Checkpoint.index.desc()).first()
    if not cp:
        cp = _create_genesis(db)
    return cp


def advance_checkpoint(db: Session, ta_ref: float) -> Checkpoint:
    """
    Advance the node to the next checkpoint.
    ta_ref is the agreed Ta value the mesh has reached.

    In v1 this is called manually by the operator.
    In v2 it triggers automatically when the mesh reaches consensus
    on the next nontrivial zeta zero index.
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
        advanced_at=datetime.utcnow()
    )
    db.add(cp)
    db.commit()
    db.refresh(cp)
    return cp


def derive_steward_key(steward_id: str, oa: float, za: float, ta: float, checkpoint_hash: str) -> str:
    """
    Derive the steward's OaZaTa-anchored API key for the given checkpoint.

    Key = sha256(steward_id | oa | za | ta | checkpoint_hash | node_secret)

    - Rotates automatically when checkpoint advances (checkpoint_hash changes)
    - ta is the steward's proper time at registration, frozen as the projection
      point — the coordinate that approximates their position at this checkpoint
    - node_secret ensures keys are node-scoped (two nodes won't issue the same key
      for the same steward position)
    - v2: ta will be replaced by the steward's full zeta spiral parameterisation
    """
    raw = f"{steward_id}|{oa}|{za}|{ta}|{checkpoint_hash}|{settings.api_key_secret}"
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return f"pm_{digest}"


def get_valid_keys_for_steward(
    steward_id: str,
    oa: float,
    za: float,
    ta: float,
    db: Session,
    grace_window: int = 2
) -> list[str]:
    """
    Return the set of currently-valid keys for a steward.

    Includes the current checkpoint key + the previous `grace_window`
    checkpoint keys so stewards aren't hard-locked mid-session during rotation.

    grace_window=2 means the key from 2 checkpoints ago is still accepted.
    """
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
        advanced_at=datetime.utcnow()
    )
    db.add(cp)
    db.commit()
    db.refresh(cp)
    return cp


def _derive_checkpoint_hash(index: int, node_id: str, prev_hash: str, ta_ref: float) -> str:
    raw = f"{index}|{node_id}|{prev_hash}|{ta_ref}"
    return hashlib.sha256(raw.encode()).hexdigest()
