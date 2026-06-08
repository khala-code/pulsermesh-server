from pydantic import BaseModel
from datetime import datetime

class StewardCreate(BaseModel):
    name: str

class StewardResponse(BaseModel):
    id: str
    name: str
    trust_resource: float
    created_at: datetime

    class Config:
        from_attributes = True
