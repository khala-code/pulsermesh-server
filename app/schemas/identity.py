from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime
from typing import Optional


class OaZaTaPosition(BaseModel):
    oa: float = 1.0
    za: float = 0.0
    ta: float = 0.0


class StewardCreateWithPosition(BaseModel):
    """
    Registration payload.

    domains       — optional declared domain cluster for mission vector
                    resolution (e.g. ["water", "energy"]).
    domain_weights— optional per-domain weights supplied by the steward.
                    Defaults to node scarcity weights if absent.
    position      — optional OaZaTa starting position; defaults to
                    (Oa=1.0, Za=0.0, Ta=0.0) if omitted.
    """
    name: str
    domains: Optional[list[str]] = None
    domain_weights: Optional[dict[str, float]] = None
    position: Optional[OaZaTaPosition] = None

    @field_validator("domains", mode="before")
    @classmethod
    def lowercase_domains(cls, v):
        if v is None:
            return v
        return [d.lower().strip() for d in v]


class IdentityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    steward_id: str
    oa: float
    za: float
    ta: float
    api_key_hash: str
    # snark fields
    mission_vector_za: Optional[float] = None
    null_centroid_za: Optional[float] = None
    mission_delta: Optional[float] = None
    pulse_count: int = 0
    # deprecated — retained for response compatibility
    position_variance: Optional[float] = None
    triangulation_count: int = 0
    created_at: datetime
