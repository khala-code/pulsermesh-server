import hashlib
from sqlalchemy.orm import Session
from app.models.identity import OaZaTaIdentity
from app.services.checkpoint import get_valid_keys_for_steward


def validate_api_key(db: Session, api_key: str):
    """
    Validate a steward's pm_ key against all currently-valid checkpoint projections.

    Iterates all active identities and checks the submitted key against the
    grace window of valid keys for each steward's frozen OaZaTa position.

    This is O(n_stewards) — fine for experimental phase.
    v2: index by checkpoint-keyed bloom filter.
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
