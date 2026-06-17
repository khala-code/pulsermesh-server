"""
app/services/domain.py — Domain Vector Service

Manages the node-local domain-to-Za mapping (DomainVector table) and
resolves steward domain clusters into Za angles for mission vector
assignment.

See docs/federation.md § 2 (Domain Vectors) and § 3 (Precession).
"""
import math
import uuid
from typing import Sequence
from sqlalchemy.orm import Session
from app.models.domain_vector import DomainVector
from app.config import settings, DEFAULT_SCARCITY_WEIGHTS


# ── seeding ──────────────────────────────────────────────────────────────────

def seed_domain_vectors(db: Session) -> list[DomainVector]:
    """
    Populate the DomainVector table from DEFAULT_SCARCITY_WEIGHTS.

    Za positions are spaced evenly around [0, 2π), ordered by the
    domain list. This gives each domain a distinct geometric position
    in the node's initial reference frame.

    Idempotent: skips domains that already have a vector for this node.
    Safe to call at application startup.
    """
    weights = settings.scarcity_weights()
    # Exclude 'default' from the evenly-spaced ring — it's a fallback,
    # not a directional domain. We still store it at Za=0.0.
    directional = {k: v for k, v in weights.items() if k != "default"}
    n = len(directional)
    existing = {
        dv.domain for dv in
        db.query(DomainVector).filter(DomainVector.node_id == settings.node_id).all()
    }

    created = []
    for i, (domain, weight) in enumerate(directional.items()):
        if domain in existing:
            continue
        za = (2 * math.pi * i) / n
        dv = DomainVector(
            id=str(uuid.uuid4()),
            domain=domain,
            za=round(za, 6),
            weight=weight,
            node_id=settings.node_id,
        )
        db.add(dv)
        created.append(dv)

    # Store the fallback 'default' domain at Za=0.0 if absent
    if "default" not in existing:
        dv = DomainVector(
            id=str(uuid.uuid4()),
            domain="default",
            za=0.0,
            weight=weights.get("default", 1.0),
            node_id=settings.node_id,
        )
        db.add(dv)
        created.append(dv)

    db.commit()
    return created


# ── lookup ───────────────────────────────────────────────────────────────────

def get_domain_za(db: Session, domain: str) -> float:
    """
    Return the Za angle for a domain on this node.
    Falls back to the 'default' domain vector if the domain is unknown.
    """
    dv = (
        db.query(DomainVector)
        .filter(
            DomainVector.domain == domain.lower(),
            DomainVector.node_id == settings.node_id
        )
        .first()
    )
    if dv:
        return dv.za

    fallback = (
        db.query(DomainVector)
        .filter(
            DomainVector.domain == "default",
            DomainVector.node_id == settings.node_id
        )
        .first()
    )
    return fallback.za if fallback else 0.0


def get_domain_vector(db: Session, domain: str) -> DomainVector | None:
    return (
        db.query(DomainVector)
        .filter(
            DomainVector.domain == domain.lower(),
            DomainVector.node_id == settings.node_id
        )
        .first()
    )


# ── mission vector resolution ───────────────────────────────────────────────

def resolve_mission_vector(
    db: Session,
    domains: Sequence[str],
    domain_weights: dict[str, float] | None = None,
) -> float:
    """
    Resolve a declared domain cluster into a single Za angle.

    Uses an Omega-weighted circular mean of the Za positions of all
    declared domains. Domain weights default to the node's scarcity
    weights if not provided by the steward.

    domain_weights  — optional per-domain amplitude weights supplied
                      by the steward at declaration time. These are
                      the steward's own weighting of their domains,
                      not the node's scarcity multipliers (though the
                      two may coincide). If absent, node weights apply.

    Returns a Za in [0, 2π).
    Returns 0.0 if no domains can be resolved.
    """
    sin_sum = 0.0
    cos_sum = 0.0
    node_weights = settings.scarcity_weights()

    for domain in domains:
        dv = get_domain_vector(db, domain)
        if dv is None:
            continue
        # Use steward-supplied weight if given, else node scarcity weight
        w = (domain_weights or {}).get(domain, node_weights.get(domain.lower(), 1.0))
        sin_sum += w * math.sin(dv.za)
        cos_sum += w * math.cos(dv.za)

    if sin_sum == 0.0 and cos_sum == 0.0:
        return 0.0

    angle = math.atan2(sin_sum, cos_sum)
    return angle % (2 * math.pi)


# ── federation seam (v2 stub) ──────────────────────────────────────────────

def negotiate_precession(
    db: Session,
    foreign_vectors: list[dict],
    foreign_oa_total: float,
) -> dict:
    """
    v2 STUB — compute merged domain vectors and per-steward precession cost.

    Does not write to the database. Returns a preview dict:

        {
            "merged_vectors": [(domain, za_merged, weight_merged), ...],
            "precession_costs": [(steward_id, cost), ...],
        }

    foreign_vectors   — list of {domain, za, weight, oa_total} dicts
                        from the remote node's DomainVector table.
    foreign_oa_total  — aggregate Ωa of all active stewards on the
                        remote node. Used as the mass weighting factor.

    Implementation note: to complete this function, the caller must
    supply the local aggregate Ωa and the per-steward (Ωa, dominant_domain)
    pairs so that C_precession(s) = |Δza_domain| · Ωa_s can be computed
    per steward. The gossip protocol layer should gather these before calling.

    See docs/federation.md § 3 and § 7.
    """
    local_vectors = (
        db.query(DomainVector)
        .filter(DomainVector.node_id == settings.node_id)
        .all()
    )
    local_oa_total = sum(  # placeholder — replace with live aggregate query
        1.0 for _ in local_vectors
    )

    foreign_map = {fv["domain"]: fv for fv in foreign_vectors}
    merged = []

    for lv in local_vectors:
        fv = foreign_map.get(lv.domain)
        if fv is None:
            merged.append((lv.domain, lv.za, lv.weight))
            continue
        # Ωa-weighted centroid
        za_merged = (
            (local_oa_total * lv.za + foreign_oa_total * fv["za"])
            / (local_oa_total + foreign_oa_total)
        )
        weight_merged = (
            (local_oa_total * lv.weight + foreign_oa_total * fv["weight"])
            / (local_oa_total + foreign_oa_total)
        )
        merged.append((lv.domain, round(za_merged, 6), round(weight_merged, 6)))

    return {
        "merged_vectors": merged,
        "precession_costs": [],  # populated by gossip layer with steward-level data
    }
