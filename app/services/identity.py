import uuid
from sqlalchemy.orm import Session
from app.models.identity import OaZaTaIdentity
from app.services.checkpoint import get_valid_keys_for_steward, get_current_checkpoint, derive_steward_key


def issue_identity(db: Session, steward_id: str, oa: float, za: float, ta: float) -> OaZaTaIdentity:
    """
    Create and persist an OaZaTa identity for a newly registered steward.
    The api_key_hash is derived from the current checkpoint — it will rotate
    as checkpoints advance.
    """
    cp = get_current_checkpoint(db)
    api_key = derive_steward_key(steward_id, oa, za, ta, cp.hash)

    identity = OaZaTaIdentity(
        id=str(uuid.uuid4()),
        steward_id=steward_id,
        oa=oa,
        za=za,
        ta=ta,
        api_key_hash=api_key
    )
    db.add(identity)
    db.commit()
    db.refresh(identity)
    return identity


def get_identity_by_steward(db: Session, steward_id: str) -> OaZaTaIdentity | None:
    return db.query(OaZaTaIdentity).filter(
        OaZaTaIdentity.steward_id == steward_id
    ).first()


def validate_api_key(db: Session, api_key: str) -> OaZaTaIdentity | None:
    """
    Validate a steward's pm_ key against all currently-valid checkpoint projections.
    Accepts keys from the current checkpoint + grace window.
    """
    identities = db.query(OaZaTaIdentity).all()
    for identity in identities:
        valid_keys = get_valid_keys_for_steward(
            steward_id=identity.steward_id,
            oa=identity.oa,
            za=identity.za,
            ta=identity.ta,
            db=db
        )
        if api_key in valid_keys:
            return identity
    return None
