from sqlalchemy import Column, String, Float, DateTime
from app.database import Base
from datetime import datetime


class Steward(Base):
    """
    A registered observer on the mesh.

    trust_resource   - accrued value from validated pulses
    coherence_score  - computed stub, populated by the trust matrix service
                       once OaZaTa position variance is measurable across
                       enough checkpoints. Range [0.0, 1.0].
                       0.0 = no data / incoherent spiral
                       1.0 = perfectly stable spiral (asymptotic target)

    Coherence is emergent from behaviour, never declared.
    It is the inverse of position variance across checkpoint triangulations.
    """
    __tablename__ = "stewards"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    trust_resource = Column(Float, default=0.0)
    coherence_score = Column(Float, default=0.0)  # stub — populated by matrix service
    created_at = Column(DateTime, default=datetime.utcnow)
