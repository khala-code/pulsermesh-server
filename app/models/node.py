from sqlalchemy import Column, String, DateTime, func
from app.database import Base

class NodeIdentity(Base):
    """This T3 node's identity record."""
    __tablename__ = "node_identity"

    id = Column(String, primary_key=True)  # node UUID
    domain = Column(String, nullable=False)  # scarcity domain label
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
