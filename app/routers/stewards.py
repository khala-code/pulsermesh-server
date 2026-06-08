import uuid
import hashlib
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth import require_api_key
from app.database import get_db
from app.models.steward import Steward
from app.schemas.steward import StewardCreate, StewardResponse

router = APIRouter()

@router.post("/register", response_model=StewardResponse)
def register_steward(
    body: StewardCreate,
    db: Session = Depends(get_db),
    api_key: str = Depends(require_api_key)
):
    """Register a new T2 steward with this T3 node."""
    steward_id = str(uuid.uuid4())
    steward = Steward(
        id=steward_id,
        name=body.name,
        api_key_hash=hashlib.sha256(steward_id.encode()).hexdigest(),
        trust_resource=0.0
    )
    db.add(steward)
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
