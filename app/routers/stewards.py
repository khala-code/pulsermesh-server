import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth import require_api_key, require_steward_key
from app.database import get_db
from app.models.steward import Steward
from app.models.identity import OaZaTaIdentity
from app.schemas.identity import StewardCreateWithPosition, OaZaTaPosition
from app.services.identity import issue_identity, get_identity_by_steward
from app.services.domain import resolve_mission_vector

router = APIRouter()


@router.post("/register")
def register_steward(
    body: StewardCreateWithPosition,
    db: Session = Depends(get_db),
    api_key: str = Depends(require_api_key)
):
    """
    Register a new T2 steward and issue their OaZaTa identity.

    If `domains` is provided, the steward's declared domain cluster is
    resolved into a mission_vector_za via the node's DomainVector table
    and stored on the identity. This is the steward's declared direction
    of travel in the geometric field.

    If no position is provided, the steward is placed at
    (Oa=1.0, Za=0.0, Ta=0.0) -- the default entry point.

    Returns steward fields plus:
      api_key           -- the plaintext pm_ key, returned once at registration only
      mission_vector_za -- resolved from declared domains if provided
    """
    steward_id = str(uuid.uuid4())
    steward = Steward(
        id=steward_id,
        name=body.name,
        trust_resource=0.0
    )
    db.add(steward)
    db.flush()

    pos = body.position or OaZaTaPosition()
    identity = issue_identity(
        db=db,
        steward_id=steward_id,
        oa=pos.oa,
        za=pos.za,
        ta=pos.ta,
    )

    # Resolve mission vector from declared domains if provided
    mission_vector_za = None
    if body.domains:
        mission_vector_za = resolve_mission_vector(
            db=db,
            domains=body.domains,
            domain_weights=body.domain_weights,
        )
        identity.mission_vector_za = mission_vector_za
        db.add(identity)

    db.commit()
    db.refresh(steward)

    return {
        "id": steward.id,
        "name": steward.name,
        "trust_resource": steward.trust_resource,
        "coherence_score": steward.coherence_score,
        "created_at": steward.created_at,
        "api_key": identity.api_key_hash,
        "mission_vector_za": mission_vector_za,
    }


@router.get("/{steward_id}")
def get_steward(
    steward_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(require_api_key)
):
    steward = db.query(Steward).filter(Steward.id == steward_id).first()
    if not steward:
        raise HTTPException(status_code=404, detail="Steward not found")
    return {
        "id": steward.id,
        "name": steward.name,
        "trust_resource": steward.trust_resource,
        "coherence_score": steward.coherence_score,
        "created_at": steward.created_at,
        "api_key": None,
        "mission_vector_za": None,
    }


@router.get("/{steward_id}/identity")
def get_steward_identity(
    steward_id: str,
    db: Session = Depends(get_db),
    identity: OaZaTaIdentity = Depends(require_steward_key)
):
    """
    Return the OaZaTa identity and snark fields for a steward.

    Accepts a steward pm_ key or the node admin key.
    """
    record = get_identity_by_steward(db, steward_id)
    if not record:
        raise HTTPException(status_code=404, detail="Identity not found")
    return {
        "id": record.id,
        "steward_id": record.steward_id,
        "oa": record.oa,
        "za": record.za,
        "ta": record.ta,
        "api_key_hash": record.api_key_hash,
        "mission_vector_za": record.mission_vector_za,
        "null_centroid_za": record.null_centroid_za,
        "mission_delta": record.mission_delta,
        "pulse_count": record.pulse_count,
        "created_at": record.created_at,
    }
