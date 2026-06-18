from sqlalchemy import Column, String, Float, DateTime, Integer
from app.database import Base
from datetime import datetime


class OaZaTaIdentity(Base):
    """
    The OaZaTa position of a steward, frozen at registration as the
    initial projection point on their zeta spiral.

    oa (Omega)  — thickness/amplitude of the orbit
    za (Zeta)   — current phase angle; updated per checkpoint advance
    ta (Tau)    — arc length along geodesic; monotonically increasing

    --- Snark / seed-structure fields ---

    mission_vector_za
        Declared direction of travel, resolved from the steward's domain
        cluster through the node's DomainVector table at registration.
        May be updated voluntarily by the steward (re-declaration).
        See docs/federation.md § 2.

    null_centroid_za
        Inferred axis of the steward's orbital curvature, computed from
        their validated pulse history graph by snark.py.
        Updated incrementally at each checkpoint advance.
        This is the Za coordinate of the hole the steward's trajectory
        is orbiting — orthogonal to their direction of travel.
        None until MIN_PULSES validated pulses exist.

    mission_delta
        |mission_vector_za - null_centroid_za| (angular, wrapped to [0, π]).
        The divergence between declared purpose and inferred trajectory.
        Convergence → coherent identity.
        Persistent divergence → genuine evolution or noise.
        None until null_centroid_za is first computed.

    pulse_count
        Number of validated pulses. This is n in uncertainty_band(n, ta)
        from asymptotic.py. Replaces triangulation_count for that purpose.

    --- Deprecated fields (retained for migration safety) ---

    position_variance
        Previously: rolling variance of triangulated position.
        Superseded by null_centroid_za + mission_delta.
        Retained so existing rows do not break on upgrade.

    triangulation_count
        Previously: number of checkpoint triangulations.
        Superseded by pulse_count.
        Retained for migration safety.
    """
    __tablename__ = "oazata_identities"

    id = Column(String, primary_key=True)
    steward_id = Column(String, nullable=False)
    oa = Column(Float, nullable=False)
    za = Column(Float, nullable=False)
    ta = Column(Float, nullable=False)
    api_key_hash = Column(String, nullable=False)

    # snark fields
    mission_vector_za = Column(Float, nullable=True, default=None)
    null_centroid_za = Column(Float, nullable=True, default=None)
    mission_delta = Column(Float, nullable=True, default=None)
    pulse_count = Column(Integer, default=0)

    # deprecated — retained for migration safety
    position_variance = Column(Float, default=None, nullable=True)
    triangulation_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
