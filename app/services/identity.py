"""OaZaTa identity issuance and validation."""
import uuid
import math
from sqlalchemy.orm import Session
from app.models.identity import OaZaTaIdentity
from app.models.steward import Steward


def issue_identity(
    db: Session,
    steward: Steward,
    oa: int = 0,
    za: float = 0.0,
    ta: float = 1.0,
    checkpoint_hash: str = "genesis"
) -> OaZaTaIdentity:
    """
    Issue an OaZaTa identity for a steward at registration.

    v1: assigns a position and derives an API key from it.
    v2: position will be validated against the T3 reference wave
        before issuance — the steward must first pass the vibe check.
    """
    api_key = OaZaTaIdentity.derive_api_key(
        steward_id=steward.id,
        oa=oa,
        za=za,
        ta=ta,
        checkpoint=checkpoint_hash
    )

    identity = OaZaTaIdentity(
        id=str(uuid.uuid4()),
        steward_id=steward.id,
        oa=oa,
        za=za,
        ta=ta,
        checkpoint_hash=checkpoint_hash,
        api_key=api_key
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
    v1: lookup identity by derived API key.
    v2: this becomes interference pattern constructive/destructive check.
    """
    return db.query(OaZaTaIdentity).filter(
        OaZaTaIdentity.api_key == api_key
    ).first()


def is_at_tan_pole(za: float, threshold: float = 1e-4) -> bool:
    """
    Check if Za is near a tangent pole (π/2 + nπ).
    Poles are structurally significant — approaching consent boundary.
    v2: pole proximity will be a signal in the vibe check, not just a guard.
    """
    return abs(math.cos(za)) < threshold
