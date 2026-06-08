from pydantic import BaseModel
from datetime import datetime

class NodeStatus(BaseModel):
    node_id: str
    domain: str
    version: str
    created_at: datetime
