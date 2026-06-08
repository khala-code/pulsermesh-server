from sqlalchemy import Column, String, Float, DateTime, Integer
from app.database import Base
from datetime import datetime, UTC


class Pulse(Base):
    """
    A value-add contribution from a steward.

    submitted_at_checkpoint - the checkpoint index when this pulse was submitted.
                              Used by T_decay to compute checkpoint_age at validation.
    """
    __tablename__ = "pulses"

    id = Column(String, primary_key=True)
    steward_id = Column(String, nullable=False)
    scarcity_domain = Column(String, nullable=False)
    description = Column(String, nullable=False)
    value_add = Column(Float, nullable=False)
    submitted_at_checkpoint = Column(Integer, nullable=True)  # None for pre-checkpoint pulses
    status = Column(String, default="pending")
    validated_at = Column(DateTime, nullable=True)
