from sqlalchemy import Column, Integer, String, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from app.database import Base
from datetime import datetime


class Checkpoint(Base):
    """
    Represents a discrete moment on the node's shared temporal reference.

    index       - monotonically increasing counter (v1 proxy for Ta progression)
    hash        - sha256 of (index + node_id + prev_hash), anchors key derivation
    ta_ref      - the Ta value the mesh agreed on at this checkpoint
    advanced_at - wall clock when the node advanced to this checkpoint

    v2: hash will be derived from a Heegner number or nontrivial zeta zero index
    so the checkpoint is externally verifiable, not just node-local.
    """
    __tablename__ = "checkpoints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    index = Column(Integer, unique=True, nullable=False)
    hash = Column(String, unique=True, nullable=False)
    ta_ref = Column(Float, nullable=False)  # agreed Ta value at this checkpoint
    advanced_at = Column(DateTime, default=datetime.utcnow)
    prev_hash = Column(String, nullable=True)  # None for genesis checkpoint
