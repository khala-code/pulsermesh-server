from sqlalchemy import Column, String, Float, DateTime, Integer
from app.database import Base
from datetime import datetime


class OaZaTaIdentity(Base):
    """
    The OaZaTa position of a steward, frozen at registration as the
    initial projection point on their zeta spiral.

    oa (Omega)  - thickness/height of the critical line at this Ta
    za (Zeta)   - mesh coupling / horizontal weighting
    ta (Tau)    - proper time axis; generally increases

    position_variance - rolling variance of triangulated OaZaTa position
                        across the last N checkpoints. Computed by the
                        matrix service. Low variance = coherent spiral.
                        Feeds directly into steward.coherence_score.

    triangulation_count - number of checkpoint triangulations performed.
                          Below a minimum threshold, coherence_score is
                          not meaningful (too few observations).
    """
    __tablename__ = "oazata_identities"

    id = Column(String, primary_key=True)
    steward_id = Column(String, nullable=False)
    oa = Column(Float, nullable=False)
    za = Column(Float, nullable=False)
    ta = Column(Float, nullable=False)
    api_key_hash = Column(String, nullable=False)
    position_variance = Column(Float, default=None, nullable=True)  # None until enough data
    triangulation_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
