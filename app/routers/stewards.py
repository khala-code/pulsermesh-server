import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth import require_api_key
from app.database import get_db
from app.models.steward import Steward
from app.schemas.identity import StewardCreateWithPosition, OaZaTaPosition
from app.schemas.steward import StewardResponse
from app.services.identity import issue_identity, get_identity_by_steward
from app.services.domain import resolve_mission_vector

router = APIRouter()


@router.post("/register", response_model=StewardResponse)
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
    (Oa=1.0, Za=0.0, Ta=0.0) — the default entry point.
    """
    steward_id = str(uuid.uuid4())
    steward = Steward(
        id=steward_id,
        name=body.name,
        api_key_hash="",
        trust_resource=0.0
    )
    db.add(steward)
    db.flush()

    pos = body.position or OaZaTaPosition()
    identity = issue_identity(
        db=db,
        steward=steward,
        oa=pos.oa,
        za=pos.za,
        ta=pos.ta,
    )

    # Resolve mission vector from declared domains if provided
    if body.domains:
        identity.mission_vector_za = resolve_mission_vector(
            db=db,
            domains=body.domains,
            domain_weights=body.domain_weights,
        )
        db.add(identity)

    steward.api_key_hash = identity.api_key
    db.commit()
    db.refresh(steward)
    return steward


@router.get("/{steward_id}", response_model=StewardResponse)
def get_steward(
    steward_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(require_api_key)
):
    steward = db.query(Steward).filter(Steward.id == steward_id).first()
    if not steward:
        raise HTTPException(status_code=404, detail="Steward not found")
    return steward


@router.get("/{steward_id}/identity")
def get_steward_identity(
    steward_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(require_api_key)
):
    """
    Return the OaZaTa identity and snark fields for a steward.
    """
    identity = get_identity_by_steward(db, steward_id)
    if not identity:
        raise HTTPException(status_code=404, detail="Identity not found")
    return {
        "id": identity.id,
        "steward_id": identity.steward_id,
        "oa": identity.oa,
        "za": identity.za,
        "ta": identity.ta,
        "api_key_hash": identity.api_key_hash,
        "mission_vector_za": identity.mission_vector_za,
        "null_centroid_za": identity.null_centroid_za,
        "mission_delta": identity.mission_delta,
        "pulse_count": identity.pulse_count,
        "created_at": identity.created_at,
    }
