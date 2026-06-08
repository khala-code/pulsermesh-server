from sqlalchemy import Column, String, Float, DateTime, func, ForeignKey
from app.database import Base

class Pulse(Base):
    """A value-add contribution submitted by a T2 steward."""
    __tablename__ = "pulses"

    id = Column(String, primary_key=True)
    steward_id = Column(String, ForeignKey("stewards.id"), nullable=False)
    scarcity_domain = Column(String, nullable=False)
    description = Column(String, nullable=False)
    value_add = Column(Float, nullable=False)  # estimated scarcity reduction
    status = Column(String, default="pending")  # pending | validated | rejected
    created_at = Column(DateTime, default=func.now())
    validated_at = Column(DateTime, nullable=True)
