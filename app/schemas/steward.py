from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class StewardCreate(BaseModel):
    name: str


class StewardResponse(BaseModel):
    id: str
    name: str
    trust_resource: float
    created_at: datetime
    # api_key_hash surfaced so the registering admin can pass it to the steward
    api_key_hash: Optional[str] = None

    class Config:
        from_attributes = True
