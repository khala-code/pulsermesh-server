import math
from sqlalchemy.orm import Session
from app.models.steward import Steward
from app.models.identity import OaZaTaIdentity
from app.services.asymptotic import coherence_score

# Minimum validated pulses before coherence_score is meaningful.
MIN_PULSES = 3


def update_coherence(db: Session, steward_id: str, za_node: float = 0.0) -> float:
    """
    Recompute and persist coherence_score for a steward.

    coherence_s = cos(ΔZa)  (docs/asymptotic-auth.md § 5)

    Returns 0.0 if fewer than MIN_PULSES have been validated.

    za_node  — the node's current Za reference; defaults to 0.0.
               Callers should pass the live node Za from the Node
               record once the node PLL is wired up.
    """
    identity = db.query(OaZaTaIdentity).filter(
        OaZaTaIdentity.steward_id == steward_id
    ).first()

    steward = db.query(Steward).filter(Steward.id == steward_id).first()

    if not identity or not steward:
        return 0.0

    if identity.triangulation_count < MIN_PULSES:
        steward.coherence_score = 0.0
        db.commit()
        return 0.0

    score = coherence_score(identity.za, za_node)
    steward.coherence_score = round(score, 6)
    db.commit()
    return steward.coherence_score
