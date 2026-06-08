from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class OaZaTaPosition(BaseModel):
    oa: float
    za: float
    ta: float


class IdentityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    steward_id: str
    oa: float
    za: float
    ta: float
    api_key_hash: str
    position_variance: Optional[float] = None
    triangulation_count: int
    created_at: datetime
