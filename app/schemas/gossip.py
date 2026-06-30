from pydantic import BaseModel, HttpUrl, field_validator
from typing import Optional
from datetime import datetime


# ---------------------------------------------------------------------------
# NodeGossip — the payload a node POSTs to /gossip on a peer
# ---------------------------------------------------------------------------

class NodeGossip(BaseModel):
    """
    Direct-HTTP gossip payload (Mode A, v1).

    The GossipEnvelope wrapper (relay metadata, broker consistency check) is a
    v2 addition and extends this as an optional outer field without breaking
    the v1 path.
    """
    node_id: str
    checkpoint_index: int
    checkpoint_hash: str
    za: float                   # sender's current phase angle (radians)
    omega_a: float              # sender's current angular velocity
    q_cross: float              # Q_cross PLL error signal at time of gossip
    phi: float                  # sender's order parameter Φ
    ta_ref: float               # sender's Ta reference at this checkpoint


# ---------------------------------------------------------------------------
# Peer management
# ---------------------------------------------------------------------------

class PeerCreate(BaseModel):
    peer_id: str
    url: str

    @field_validator("peer_id")
    @classmethod
    def peer_id_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("peer_id must not be blank")
        return v.strip()

    @field_validator("url")
    @classmethod
    def url_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("url must not be blank")
        return v.strip()


class PeerRead(BaseModel):
    peer_id: str
    url: str
    added_at: datetime
    last_seen_checkpoint: Optional[int] = None
    last_seen_at: Optional[datetime] = None
    anomaly_count: int

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# GossipLog read schema (operator / observability)
# ---------------------------------------------------------------------------

class GossipLogRead(BaseModel):
    id: int
    direction: str
    peer_id: str
    checkpoint_index: int
    delivered: bool
    q_cross: Optional[float] = None
    sign_flip: Optional[bool] = None
    anomaly_flagged: bool
    raw_node_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
