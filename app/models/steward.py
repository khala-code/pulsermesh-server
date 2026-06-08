from sqlalchemy import Column, String, Float, DateTime, func
from app.database import Base

class Steward(Base):
    """A registered T2 steward submitting work into this T3 domain."""
    __tablename__ = "stewards"

    id = Column(String, primary_key=True)  # steward UUID
    name = Column(String, nullable=False)
    api_key_hash = Column(String, nullable=False)
    trust_resource = Column(Float, default=0.0)  # accumulated trust-resource
    created_at = Column(DateTime, default=func.now())
