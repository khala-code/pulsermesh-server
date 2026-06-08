from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class PulseCreate(BaseModel):
    scarcity_domain: str
    description: str
    value_add: float

class PulseResponse(BaseModel):
    id: str
    steward_id: str
    scarcity_domain: str
    description: str
    value_add: float
    status: str
    created_at: datetime
    validated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
