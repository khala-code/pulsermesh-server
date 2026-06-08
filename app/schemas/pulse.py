from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class PulseCreate(BaseModel):
    scarcity_domain: str
    description: str
    value_add: float


class PulseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    steward_id: str
    scarcity_domain: str
    description: str
    value_add: float
    submitted_at_checkpoint: Optional[int] = None
    status: str
    validated_at: Optional[datetime] = None
