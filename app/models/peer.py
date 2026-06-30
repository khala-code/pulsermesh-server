from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.database import Base
from datetime import datetime


class Peer(Base):
    """
    A known remote node this node gossips with (Mode A: direct HTTP).

    peer_id               - the remote node's node_id (hex digest)
    url                   - base URL for POST /gossip delivery
    added_at              - when this peer was registered
    last_seen_checkpoint  - the checkpoint index we last successfully delivered to
    last_seen_at          - wall clock of last successful delivery
    anomaly_count         - operator-incremented manual signal; non-zero flags
                            this peer for closer observation.  Not used in any
                            automated eviction logic in v1 — purely observational.

    v2: steward-mediated peer discovery will populate this table automatically
    via the GossipEnvelope relay metadata path.
    """
    __tablename__ = "peers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    peer_id = Column(String, unique=True, nullable=False, index=True)
    url = Column(String, nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_checkpoint = Column(Integer, nullable=True)   # None until first successful delivery
    last_seen_at = Column(DateTime, nullable=True)
    anomaly_count = Column(Integer, default=0, nullable=False)
