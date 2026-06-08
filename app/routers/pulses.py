import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth import require_steward_key, require_api_key
from app.database import get_db
from app.models.pulse import Pulse
from app.models.steward import Steward
from app.models.identity import OaZaTaIdentity
from app.schemas.pulse import PulseCreate, PulseResponse
from app.services.trust import calculate_trust_delta
from app.config import settings
from datetime import datetime, UTC

router = APIRouter()


@router.post("/submit", response_model=PulseResponse)
def submit_pulse(
    body: PulseCreate,
    db: Session = Depends(get_db),
    identity: OaZaTaIdentity = Depends(require_steward_key)
):
    if identity is None:
        raise HTTPException(status_code=400, detail="Use a steward API key to submit pulses")

    steward = db.query(Steward).filter(Steward.id == identity.steward_id).first()
    if not steward:
        raise HTTPException(status_code=404, detail="Steward not found")

    pulse = Pulse(
        id=str(uuid.uuid4()),
        steward_id=steward.id,
        scarcity_domain=body.scarcity_domain,
        description=body.description,
        value_add=body.value_add,
        status="pending"
    )
    db.add(pulse)
    db.commit()
    db.refresh(pulse)
    return pulse


@router.post("/{pulse_id}/validate", response_model=PulseResponse)
def validate_pulse(
    pulse_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(require_api_key)
):
    pulse = db.query(Pulse).filter(Pulse.id == pulse_id).first()
    if not pulse:
        raise HTTPException(status_code=404, detail="Pulse not found")
    if pulse.status != "pending":
        raise HTTPException(status_code=400, detail="Pulse already processed")

    steward = db.query(Steward).filter(Steward.id == pulse.steward_id).first()

    # T_scarcity transform — domain weight applied at validation time
    delta = calculate_trust_delta(
        value_add=pulse.value_add,
        scarcity_domain=pulse.scarcity_domain,
        scarcity_weights=settings.scarcity_weights()
    )
    steward.trust_resource += delta

    pulse.status = "validated"
    pulse.validated_at = datetime.now(UTC)

    db.commit()
    db.refresh(pulse)
    return pulse


@router.get("/mine", response_model=list[PulseResponse])
def get_my_pulses(
    db: Session = Depends(get_db),
    identity: OaZaTaIdentity = Depends(require_steward_key)
):
    if identity is None:
        raise HTTPException(status_code=400, detail="Use a steward API key")
    return db.query(Pulse).filter(Pulse.steward_id == identity.steward_id).all()


@router.get("/{pulse_id}", response_model=PulseResponse)
def get_pulse(
    pulse_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(require_api_key)
):
    pulse = db.query(Pulse).filter(Pulse.id == pulse_id).first()
    if not pulse:
        raise HTTPException(status_code=404, detail="Pulse not found")
    return pulse
