from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float
from app.database import Base
from datetime import datetime


class GossipLog(Base):
    """
    Immutable record of every gossip event — inbound and outbound.

    direction        - 'inbound' or 'outbound'
    peer_id          - the remote node involved
    checkpoint_index - the checkpoint this gossip carried
    delivered        - True if POST succeeded (outbound) or payload was accepted (inbound)
    q_cross          - Q_cross value extracted from the inbound NodeGossip (inbound only)
    sign_flip        - True if a phase sign-flip was detected on receipt (inbound only)
    anomaly_flagged  - True if this event was flagged as anomalous (e.g. repeated sign-flip,
                       delivered=False streak).  Set by gossip service, read by operator.
    raw_node_id      - the node_id field from the inbound NodeGossip payload (inbound only)
    created_at       - wall clock of the event

    Design note: this table is append-only.  Nothing in v1 deletes or updates rows.
    Retention policy (e.g. keep last N checkpoints) is a v2 operator concern.
    """
    __tablename__ = "gossip_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    direction = Column(String, nullable=False)          # 'inbound' | 'outbound'
    peer_id = Column(String, nullable=False, index=True)
    checkpoint_index = Column(Integer, nullable=False, index=True)
    delivered = Column(Boolean, nullable=False)
    q_cross = Column(Float, nullable=True)              # inbound only
    sign_flip = Column(Boolean, nullable=True)          # inbound only
    anomaly_flagged = Column(Boolean, default=False, nullable=False)
    raw_node_id = Column(String, nullable=True)         # inbound only
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
