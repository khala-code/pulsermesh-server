import math
import uuid
import hashlib
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, func
from app.database import Base


class OaZaTaIdentity(Base):
    """
    OaZaTa field position descriptor.

    An identity in the Pulser Mesh is not a static string — it is a position
    in the trust-resource field at a given checkpoint:

        Oa  — depth layer (integer Heegner tier)
        Za  — phase angle from domain centroid (radians)
        Ta  — radial distance from the Kleiniön root

    v1: serialized to an API key string for compatibility.
    v2: replaced by interference pattern proof against the T3 reference wave.
    """
    __tablename__ = "oazata_identities"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    steward_id = Column(String, ForeignKey("stewards.id"), nullable=False, unique=True)

    # Field position
    oa = Column(Integer, default=0)       # depth layer
    za = Column(Float, default=0.0)       # phase angle (radians, 0 to 2π)
    ta = Column(Float, default=1.0)       # radial distance from root (> 0)

    # Checkpoint this identity was issued at
    checkpoint_hash = Column(String, nullable=False, default="genesis")

    # v1 API key derived from position
    api_key = Column(String, unique=True, nullable=False)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    @staticmethod
    def derive_api_key(steward_id: str, oa: int, za: float, ta: float, checkpoint: str) -> str:
        """
        v1: derive a deterministic API key from the OaZaTa position.
        v2: this becomes the interference pattern proof generator.

        The key encodes the triadic rotor phase:
            sin(za)  → real bond to domain
            cos(za)  → imaginary/predictive bond
            tan(za)  → consent coupling ratio (undefined at poles — intentional)
        """
        # Avoid tan pole — nudge if za is at π/2 or 3π/2
        safe_za = za
        pole_threshold = 1e-6
        if abs(math.cos(safe_za)) < pole_threshold:
            safe_za += pole_threshold

        sin_z = math.sin(safe_za)
        cos_z = math.cos(safe_za)
        tan_z = math.tan(safe_za)

        # Interference fingerprint: position × rotor phase
        fingerprint = f"{steward_id}|oa={oa}|za={za:.8f}|ta={ta:.8f}|sin={sin_z:.8f}|cos={cos_z:.8f}|tan={tan_z:.8f}|cp={checkpoint}"
        return "pm_" + hashlib.sha256(fingerprint.encode()).hexdigest()

    @property
    def rotor_phase(self) -> dict:
        """Return the triadic rotor decomposition of the current Za position."""
        safe_za = self.za
        if abs(math.cos(safe_za)) < 1e-6:
            safe_za += 1e-6
        return {
            "sin": math.sin(safe_za),   # real bond
            "cos": math.cos(safe_za),   # imaginary bond
            "tan": math.tan(safe_za),   # consent coupling
            "za": self.za,
            "ta": self.ta,
            "oa": self.oa,
        }
