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
from datetime import datetime

router = APIRouter()


@router.post("/submit", response_model=PulseResponse)
def submit_pulse(
    body: PulseCreate,
    db: Session = Depends(get_db),
    identity: OaZaTaIdentity = Depends(require_steward_key)
):
    """
    Submit a value-add pulse. Auth is steward-scoped — the steward
    is resolved from their OaZaTa API key, no need to pass steward_id.

    Node admin key also accepted (returns 400 if no steward context).
    """
    if identity is None:
        raise HTTPException(
            status_code=400,
            detail="Use a steward API key to submit pulses, not the node key"
        )

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
    api_key: str = Depends(require_api_key)  # node-level only
):
    """
    Validate a pending pulse. Node-level operation only —
    T3 node operator confirms the value-add and accrues trust-resource.
    """
    pulse = db.query(Pulse).filter(Pulse.id == pulse_id).first()
    if not pulse:
        raise HTTPException(status_code=404, detail="Pulse not found")
    if pulse.status != "pending":
        raise HTTPException(status_code=400, detail="Pulse already processed")

    steward = db.query(Steward).filter(Steward.id == pulse.steward_id).first()
    delta = calculate_trust_delta(pulse.value_add)
    steward.trust_resource += delta

    pulse.status = "validated"
    pulse.validated_at = datetime.utcnow()

    db.commit()
    db.refresh(pulse)
    return pulse


@router.get("/mine", response_model=list[PulseResponse])
def get_my_pulses(
    db: Session = Depends(get_db),
    identity: OaZaTaIdentity = Depends(require_steward_key)
):
    """Return all pulses submitted by the authenticated steward."""
    if identity is None:
        raise HTTPException(status_code=400, detail="Use a steward API key")
    pulses = db.query(Pulse).filter(Pulse.steward_id == identity.steward_id).all()
    return pulses


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
