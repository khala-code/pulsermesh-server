"""
app/services/snark.py — Snark / Seed-Structure Service

Builds the boundary-observable pulse history graph for a steward,
infers the null centroid of their orbital trajectory, and computes
the mission delta: the angular divergence between declared purpose
and inferred direction of travel.

Key concepts:

  Null centroid
      The Za axis around which the steward's pulse history orbits.
      Computed from the arc of their Za positions across checkpoints
      and domains — never from a direct measurement. More pulses
      tighten the constraint (see uncertainty_radius()).

  Mission delta
      |mission_vector_za − null_centroid_za| wrapped to [0, π].
      Convergence = coherent identity (declared matches inferred).
      Persistent divergence = evolution in progress or noise.

  Boundary only
      Interior activity (pulse description, free text) is never read.
      Only (checkpoint, domain, trust_delta, Za) tuples enter the graph.
      This mirrors the holographic principle: the surface reading encodes
      what matters structurally; the interior washes out.

See docs/federation.md § 2 and docs/asymptotic-auth.md § 4–6.
"""
import math
import uuid
from dataclasses import dataclass
from typing import Any
from sqlalchemy.orm import Session
from app.models.identity import OaZaTaIdentity
from app.models.pulse import Pulse
from app.services.domain import get_domain_za
from app.services import asymptotic


# ── constants ───────────────────────────────────────────────────────────────────

# Minimum validated pulses before the null centroid is computed.
# Below this threshold null_centroid_za stays None — the arc is too
# short to meaningfully infer an orbital axis.
MIN_CENTROID_PULSES: int = 5

# Cross-domain edge threshold in the pulse graph: two pulses in
# different domains at the same checkpoint are connected if their
# Za positions are within this angular distance (radians).
PROXIMITY_THRESHOLD: float = math.pi / 6  # 30 degrees


# ── data structures ──────────────────────────────────────────────────────────────

@dataclass
class PulseVertex:
    """A single node in the pulse history graph."""
    checkpoint: int
    domain: str
    za: float           # domain Za in node frame at time of pulse
    trust_delta: float  # value_add · domain_weight (the boundary observable)


@dataclass
class PulseEdge:
    """A directed edge in the pulse history graph."""
    source: PulseVertex
    target: PulseVertex
    weight: float       # trust_delta of source vertex
    edge_type: str      # 'sequential' | 'proximity'


@dataclass
class PulseGraph:
    vertices: list[PulseVertex]
    edges: list[PulseEdge]


@dataclass
class SnarkUpdate:
    steward_id: str
    pulse_count: int
    null_centroid_za: float | None
    mission_delta: float | None
    uncertainty_radius: float


# ── graph construction ────────────────────────────────────────────────────────────

def _build_pulse_graph(
    db: Session,
    steward_id: str,
    from_checkpoint: int = 0,
) -> PulseGraph:
    """
    Build the boundary-observable pulse history graph for a steward.

    Reads only validated pulses with a submitted_at_checkpoint value.
    Interior fields (description) are not accessed.

    Vertex: (checkpoint, domain) pair.
    Edges:
      sequential  — same domain, consecutive checkpoints.
      proximity   — different domains, same checkpoint, |Za_i - Za_j|
                    < PROXIMITY_THRESHOLD.

    from_checkpoint allows partial rebuilds (e.g., last N checkpoints)
    but the default is to build from the full history for centroid
    accuracy. The centroid computation is O(n) in validated pulse count
    so full history is tractable for foreseeable steward lifetimes.
    """
    pulses = (
        db.query(Pulse)
        .filter(
            Pulse.steward_id == steward_id,
            Pulse.status == "validated",
            Pulse.submitted_at_checkpoint >= from_checkpoint,
            Pulse.submitted_at_checkpoint.isnot(None),
        )
        .order_by(Pulse.submitted_at_checkpoint.asc())
        .all()
    )

    # Build vertices: one per validated pulse
    vertices: list[PulseVertex] = []
    for p in pulses:
        za = get_domain_za(db, p.scarcity_domain)
        # trust_delta: value_add is the boundary-observable magnitude
        # scarcity weight is baked into the domain Za position, so
        # we use raw value_add here to avoid double-counting.
        vertices.append(PulseVertex(
            checkpoint=p.submitted_at_checkpoint,
            domain=p.scarcity_domain,
            za=za,
            trust_delta=p.value_add,
        ))

    edges: list[PulseEdge] = []

    # Sequential edges: same domain, sorted by checkpoint
    domain_history: dict[str, list[PulseVertex]] = {}
    for v in vertices:
        domain_history.setdefault(v.domain, []).append(v)

    for domain_verts in domain_history.values():
        for i in range(len(domain_verts) - 1):
            edges.append(PulseEdge(
                source=domain_verts[i],
                target=domain_verts[i + 1],
                weight=domain_verts[i].trust_delta,
                edge_type="sequential",
            ))

    # Proximity edges: different domains, same checkpoint
    checkpoint_groups: dict[int, list[PulseVertex]] = {}
    for v in vertices:
        checkpoint_groups.setdefault(v.checkpoint, []).append(v)

    for cp_verts in checkpoint_groups.values():
        for i, vi in enumerate(cp_verts):
            for vj in cp_verts[i + 1:]:
                if vi.domain == vj.domain:
                    continue
                dist = _angular_distance(vi.za, vj.za)
                if dist < PROXIMITY_THRESHOLD:
                    edges.append(PulseEdge(
                        source=vi,
                        target=vj,
                        weight=(vi.trust_delta + vj.trust_delta) / 2,
                        edge_type="proximity",
                    ))

    return PulseGraph(vertices=vertices, edges=edges)


# ── centroid inference ────────────────────────────────────────────────────────────

def infer_null_centroid(graph: PulseGraph) -> float | None:
    """
    Infer the Za axis of the steward's orbital curvature.

    Uses a trust-delta-weighted circular mean of all validated pulse
    Za positions in the graph.

    The analogy: you find the centre of a circle from arc data alone,
    not by visiting the centre. Each pulse is a point on the arc; the
    centroid is where the curvature converges.

    Returns None if fewer than MIN_CENTROID_PULSES vertices exist.
    Returns a Za in [0, 2π).
    """
    if len(graph.vertices) < MIN_CENTROID_PULSES:
        return None

    sin_sum = 0.0
    cos_sum = 0.0
    for v in graph.vertices:
        w = max(v.trust_delta, 1e-9)  # guard against zero-weight vertices
        sin_sum += w * math.sin(v.za)
        cos_sum += w * math.cos(v.za)

    if sin_sum == 0.0 and cos_sum == 0.0:
        return None

    angle = math.atan2(sin_sum, cos_sum)
    return angle % (2 * math.pi)


# ── mission delta ─────────────────────────────────────────────────────────────────

def _angular_distance(a: float, b: float) -> float:
    """
    Angular distance between two Za angles, wrapped to [0, π].
    This is the shortest arc between them on the unit circle.
    """
    diff = abs(a - b) % (2 * math.pi)
    return min(diff, 2 * math.pi - diff)


def compute_mission_delta(
    mission_vector_za: float | None,
    null_centroid_za: float | None,
) -> float | None:
    """
    Angular divergence between declared and inferred direction.

    Returns None if either value is absent.
    Returns a value in [0, π]:
      0   — declared and inferred are perfectly aligned
      π/2 — orthogonal; steward is doing something adjacent to their stated purpose
      π   — maximally divergent
    """
    if mission_vector_za is None or null_centroid_za is None:
        return None
    return _angular_distance(mission_vector_za, null_centroid_za)


# ── uncertainty radius ─────────────────────────────────────────────────────────────

def uncertainty_radius(identity: OaZaTaIdentity) -> float:
    """
    Angular radius of the uncertainty band around the null centroid.

    Delegates to asymptotic.uncertainty_band(n, ta) using the
    identity's pulse_count and ta as the two scaling parameters.

    The snark adds a structural tightening: the band narrows by a
    factor proportional to sqrt(pulse_count) beyond what the raw
    asymptotic band provides. This reflects that each validated pulse
    is an additional constraint on the centroid position, not just on
    the authentication window.

    A steward with 3 pulses has a wide, uncertain centroid estimate.
    A steward with 300 pulses has a tight, well-constrained one.
    """
    n = max(identity.pulse_count, 1)
    ta = identity.ta
    base_band = asymptotic.uncertainty_band(n, ta)
    # Structural narrowing: each additional pulse tightens beyond the
    # base 1/sqrt(n) decay. The sqrt(n) factor in the denominator
    # compounds with the existing 1/sqrt(n) in uncertainty_band to
    # give 1/n total decay for the centroid radius.
    return base_band / math.sqrt(n)


# ── main update entrypoint ──────────────────────────────────────────────────────────

def update_snark_identity(
    db: Session,
    steward_id: str,
    identity: OaZaTaIdentity,
) -> SnarkUpdate:
    """
    Recompute the snark fields for a steward at checkpoint advance.

    Called by checkpoint.py after trust and Za updates are committed.
    Reads the full validated pulse history, infers the null centroid,
    recomputes mission delta, and writes the updated fields to the
    identity row.

    Returns a SnarkUpdate dataclass with the new values for logging
    and downstream use by coherence.py.
    """
    graph = _build_pulse_graph(db, steward_id)

    # Count only pulses that entered the graph (validated + checkpointed)
    pulse_count = len(graph.vertices)
    identity.pulse_count = pulse_count

    null_centroid = infer_null_centroid(graph)
    identity.null_centroid_za = null_centroid

    delta = compute_mission_delta(identity.mission_vector_za, null_centroid)
    identity.mission_delta = delta

    db.add(identity)
    db.commit()
    db.refresh(identity)

    radius = uncertainty_radius(identity)

    return SnarkUpdate(
        steward_id=steward_id,
        pulse_count=pulse_count,
        null_centroid_za=null_centroid,
        mission_delta=delta,
        uncertainty_radius=radius,
    )
