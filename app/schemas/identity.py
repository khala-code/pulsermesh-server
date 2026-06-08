from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class OaZaTaPosition(BaseModel):
    oa: int = 0
    za: float = 0.0
    ta: float = 1.0


class IdentityResponse(BaseModel):
    id: str
    steward_id: str
    oa: int
    za: float
    ta: float
    checkpoint_hash: str
    api_key: str
    rotor_phase: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class StewardCreateWithPosition(BaseModel):
    name: str
    position: Optional[OaZaTaPosition] = None
