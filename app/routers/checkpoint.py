from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth import require_api_key
from app.database import get_db
from app.services.checkpoint import get_current_checkpoint, advance_checkpoint
from pydantic import BaseModel

router = APIRouter()


class AdvanceRequest(BaseModel):
    ta_ref: float


class CheckpointResponse(BaseModel):
    index: int
    hash: str
    ta_ref: float
    advanced_at: str
    prev_hash: str | None

    class Config:
        from_attributes = True


@router.get("/current", response_model=CheckpointResponse)
def current_checkpoint(
    db: Session = Depends(get_db),
    api_key: str = Depends(require_api_key)
):
    """Return the node's current checkpoint."""
    cp = get_current_checkpoint(db)
    return CheckpointResponse(
        index=cp.index,
        hash=cp.hash,
        ta_ref=cp.ta_ref,
        advanced_at=cp.advanced_at.isoformat(),
        prev_hash=cp.prev_hash
    )


@router.post("/advance", response_model=CheckpointResponse)
def advance(
    body: AdvanceRequest,
    db: Session = Depends(get_db),
    api_key: str = Depends(require_api_key)  # node admin only
):
    """
    Manually advance the checkpoint to the next index.
    ta_ref is the agreed proper-time value the mesh has reached.

    v2: this will require mesh consensus before advancing.
    """
    if body.ta_ref < 0:
        raise HTTPException(status_code=400, detail="ta_ref must be non-negative")
    cp = advance_checkpoint(db, body.ta_ref)
    return CheckpointResponse(
        index=cp.index,
        hash=cp.hash,
        ta_ref=cp.ta_ref,
        advanced_at=cp.advanced_at.isoformat(),
        prev_hash=cp.prev_hash
    )
