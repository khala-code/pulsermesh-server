from fastapi import APIRouter, Depends
from app.auth import require_api_key
from app.config import settings
from app.schemas.node import NodeStatus
from datetime import datetime

router = APIRouter()

@router.get("/status", response_model=NodeStatus)
def get_node_status(api_key: str = Depends(require_api_key)):
    """Return this T3 node's identity and status."""
    return NodeStatus(
        node_id=settings.node_id or "unregistered",
        domain=settings.node_domain or "unset",
        version="0.1.0",
        created_at=datetime.utcnow()
    )
