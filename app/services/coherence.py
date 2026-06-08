import math
from sqlalchemy.orm import Session
from app.models.steward import Steward
from app.models.identity import OaZaTaIdentity

# Minimum triangulations before coherence_score is meaningful
MIN_TRIANGULATIONS = 3


def update_coherence(db: Session, steward_id: str) -> float:
    """
    Recompute and persist coherence_score for a steward.

    Coherence = 1 / (1 + position_variance)
    - variance=0.0  → coherence=1.0  (perfect spiral stability)
    - variance=inf  → coherence=0.0  (fully incoherent)

    Returns 0.0 if fewer than MIN_TRIANGULATIONS have been performed.

    This is a stub — position_variance is currently set externally by
    the matrix service. This function just translates it into the
    [0,1] coherence score and writes it to the steward record.
    """
    identity = db.query(OaZaTaIdentity).filter(
        OaZaTaIdentity.steward_id == steward_id
    ).first()

    steward = db.query(Steward).filter(Steward.id == steward_id).first()

    if not identity or not steward:
        return 0.0

    if identity.triangulation_count < MIN_TRIANGULATIONS:
        steward.coherence_score = 0.0
        db.commit()
        return 0.0

    if identity.position_variance is None:
        steward.coherence_score = 0.0
        db.commit()
        return 0.0

    score = 1.0 / (1.0 + identity.position_variance)
    steward.coherence_score = round(score, 6)
    db.commit()
    return steward.coherence_score
