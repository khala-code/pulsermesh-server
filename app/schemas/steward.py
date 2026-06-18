from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class StewardCreate(BaseModel):
    name: str


class StewardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    trust_resource: float
    coherence_score: float
    created_at: datetime
    api_key: Optional[str] = None
    mission_vector_za: Optional[float] = None
