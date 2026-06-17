from sqlalchemy import Column, String, Float, DateTime, UniqueConstraint
from app.database import Base
from datetime import datetime


class DomainVector(Base):
    """
    Node-local assignment of a Za angle and scarcity weight to a domain string.

    The Za angle places this domain in the node's geometric reference frame.
    Two nodes may assign the same domain string to different Za positions —
    that divergence is the precession problem resolved at federation time.

    See docs/federation.md § 2 (Domain Vectors) and § 3 (Precession).

    weight    — scarcity multiplier; mirrors the existing scarcity_weights
                dict in config.py. DomainVector is the persistent, per-node
                source of truth that replaces the in-memory dict for any
                computation that also needs the Za angle.

    za        — angular position of this domain in [0, 2π).
                At node initialisation, domains are seeded with evenly
                spaced Za values derived from DEFAULT_SCARCITY_WEIGHTS.
                They drift over time as the node's PLL tunes its Za_n.

    node_id   — the node this vector belongs to. Supports the federation
                seam: a foreign domain vector table can be loaded alongside
                this one for precession computation without overwriting it.
    """
    __tablename__ = "domain_vectors"
    __table_args__ = (
        UniqueConstraint("domain", "node_id", name="uq_domain_node"),
    )

    id = Column(String, primary_key=True)
    domain = Column(String, nullable=False, index=True)
    za = Column(Float, nullable=False)          # angular position in node frame
    weight = Column(Float, nullable=False, default=1.0)  # scarcity multiplier
    node_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
