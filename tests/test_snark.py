"""
tests/test_snark.py — pure function tests for snark.py

No database required: tests operate on PulseVertex / PulseGraph
dataclasses directly and mock the DB lookup in _build_pulse_graph.
"""
import math
import pytest
from unittest.mock import MagicMock, patch
from app.services.snark import (
    _angular_distance,
    compute_mission_delta,
    infer_null_centroid,
    PulseVertex,
    PulseGraph,
    MIN_CENTROID_PULSES,
    PROXIMITY_THRESHOLD,
    _build_pulse_graph,
    uncertainty_radius,
)
from app.models.identity import OaZaTaIdentity


# ── _angular_distance ───────────────────────────────────────────────────────────

def test_angular_distance_zero():
    assert _angular_distance(0.0, 0.0) == 0.0


def test_angular_distance_pi():
    assert abs(_angular_distance(0.0, math.pi) - math.pi) < 1e-9


def test_angular_distance_symmetric():
    a, b = 0.5, 2.1
    assert abs(_angular_distance(a, b) - _angular_distance(b, a)) < 1e-9


def test_angular_distance_wraps_correctly():
    # 2π - 0.1 and 0.1 are 0.2 apart, not 2π - 0.2 apart
    assert abs(_angular_distance(2 * math.pi - 0.1, 0.1) - 0.2) < 1e-6


def test_angular_distance_max_is_pi():
    for a in [0.0, 0.5, 1.0, 2.0, 3.0]:
        for b in [0.0, 0.5, 1.5, 2.5, 3.5]:
            assert _angular_distance(a, b) <= math.pi + 1e-9


# ── compute_mission_delta ──────────────────────────────────────────────────────

def test_mission_delta_none_if_mission_vector_missing():
    assert compute_mission_delta(None, 1.0) is None


def test_mission_delta_none_if_centroid_missing():
    assert compute_mission_delta(1.0, None) is None


def test_mission_delta_zero_when_aligned():
    assert abs(compute_mission_delta(1.0, 1.0)) < 1e-9


def test_mission_delta_pi_when_opposite():
    assert abs(compute_mission_delta(0.0, math.pi) - math.pi) < 1e-9


def test_mission_delta_in_range():
    import random
    rng = random.Random(42)
    for _ in range(50):
        a = rng.uniform(0, 2 * math.pi)
        b = rng.uniform(0, 2 * math.pi)
        delta = compute_mission_delta(a, b)
        assert 0.0 <= delta <= math.pi + 1e-9


# ── infer_null_centroid ───────────────────────────────────────────────────────────

def _make_vertices(za_list: list[float], weight: float = 1.0, checkpoint: int = 1) -> list[PulseVertex]:
    return [
        PulseVertex(checkpoint=checkpoint + i, domain="water", za=za, trust_delta=weight)
        for i, za in enumerate(za_list)
    ]


def test_centroid_none_below_min_pulses():
    verts = _make_vertices([0.5] * (MIN_CENTROID_PULSES - 1))
    graph = PulseGraph(vertices=verts, edges=[])
    assert infer_null_centroid(graph) is None


def test_centroid_computed_at_min_pulses():
    za = 1.2
    verts = _make_vertices([za] * MIN_CENTROID_PULSES)
    graph = PulseGraph(vertices=verts, edges=[])
    result = infer_null_centroid(graph)
    assert result is not None
    assert abs(result - za) < 1e-6


def test_centroid_cluster_at_same_za():
    za = 2.5
    verts = _make_vertices([za] * 10)
    graph = PulseGraph(vertices=verts, edges=[])
    result = infer_null_centroid(graph)
    assert abs(result - za) < 1e-5


def test_centroid_weighted_toward_heavier_side():
    # Two clusters: Za=0.3 (weight=3) and Za=2.0 (weight=1)
    # Centroid should be closer to 0.3
    heavy = [PulseVertex(checkpoint=i, domain="water", za=0.3, trust_delta=3.0) for i in range(5)]
    light = [PulseVertex(checkpoint=i + 10, domain="energy", za=2.0, trust_delta=1.0) for i in range(5)]
    graph = PulseGraph(vertices=heavy + light, edges=[])
    result = infer_null_centroid(graph)
    assert result is not None
    dist_to_heavy = _angular_distance(result, 0.3)
    dist_to_light = _angular_distance(result, 2.0)
    assert dist_to_heavy < dist_to_light


def test_centroid_result_in_range():
    import random
    rng = random.Random(7)
    verts = [
        PulseVertex(checkpoint=i, domain="water", za=rng.uniform(0, 2 * math.pi), trust_delta=rng.uniform(0.1, 5.0))
        for i in range(20)
    ]
    graph = PulseGraph(vertices=verts, edges=[])
    result = infer_null_centroid(graph)
    assert result is not None
    assert 0.0 <= result < 2 * math.pi


# ── _build_pulse_graph ────────────────────────────────────────────────────────────

def _make_pulse(steward_id, domain, value_add, checkpoint, status="validated"):
    from app.models.pulse import Pulse
    import uuid
    p = Pulse()
    p.id = str(uuid.uuid4())
    p.steward_id = steward_id
    p.scarcity_domain = domain
    p.value_add = value_add
    p.submitted_at_checkpoint = checkpoint
    p.status = status
    p.description = "test"
    return p


def test_graph_sequential_edges(db):
    from app.services.domain import seed_domain_vectors
    seed_domain_vectors(db)

    sid = "steward-1"
    pulses = [
        _make_pulse(sid, "water", 1.0, 1),
        _make_pulse(sid, "water", 1.0, 2),
        _make_pulse(sid, "water", 1.0, 3),
    ]
    for p in pulses:
        db.add(p)
    db.commit()

    graph = _build_pulse_graph(db, sid)
    sequential = [e for e in graph.edges if e.edge_type == "sequential"]
    assert len(sequential) == 2  # 3 pulses -> 2 sequential edges


def test_graph_proximity_edge_created_within_threshold(db):
    from app.services.domain import seed_domain_vectors, get_domain_za
    from app.models.domain_vector import DomainVector
    import uuid
    seed_domain_vectors(db)

    # Force two domains to be close in Za
    from app.config import settings
    za_base = 1.0
    for domain, offset in [("water", 0.0), ("energy", PROXIMITY_THRESHOLD * 0.5)]:
        dv = db.query(DomainVector).filter(
            DomainVector.domain == domain,
            DomainVector.node_id == settings.node_id
        ).first()
        dv.za = za_base + offset
    db.commit()

    sid = "steward-2"
    pulses = [
        _make_pulse(sid, "water", 1.0, 1),
        _make_pulse(sid, "energy", 1.0, 1),  # same checkpoint
    ]
    for p in pulses:
        db.add(p)
    db.commit()

    graph = _build_pulse_graph(db, sid)
    proximity = [e for e in graph.edges if e.edge_type == "proximity"]
    assert len(proximity) >= 1


def test_graph_no_proximity_edge_above_threshold(db):
    from app.services.domain import seed_domain_vectors
    from app.models.domain_vector import DomainVector
    from app.config import settings
    seed_domain_vectors(db)

    # Force two domains far apart in Za
    for domain, za in [("water", 0.0), ("energy", math.pi)]:
        dv = db.query(DomainVector).filter(
            DomainVector.domain == domain,
            DomainVector.node_id == settings.node_id
        ).first()
        dv.za = za
    db.commit()

    sid = "steward-3"
    pulses = [
        _make_pulse(sid, "water", 1.0, 1),
        _make_pulse(sid, "energy", 1.0, 1),
    ]
    for p in pulses:
        db.add(p)
    db.commit()

    graph = _build_pulse_graph(db, sid)
    proximity = [e for e in graph.edges if e.edge_type == "proximity"]
    assert len(proximity) == 0


def test_graph_ignores_unvalidated_pulses(db):
    from app.services.domain import seed_domain_vectors
    seed_domain_vectors(db)

    sid = "steward-4"
    pulses = [
        _make_pulse(sid, "water", 1.0, 1, status="pending"),
        _make_pulse(sid, "water", 1.0, 2, status="validated"),
    ]
    for p in pulses:
        db.add(p)
    db.commit()

    graph = _build_pulse_graph(db, sid)
    assert len(graph.vertices) == 1


# ── uncertainty_radius ────────────────────────────────────────────────────────────

def _make_identity(pulse_count: int, ta: float = 10.0) -> OaZaTaIdentity:
    identity = OaZaTaIdentity()
    identity.id = "test-id"
    identity.steward_id = "test-steward"
    identity.oa = 1.0
    identity.za = 0.0
    identity.ta = ta
    identity.api_key_hash = "hash"
    identity.pulse_count = pulse_count
    return identity


def test_uncertainty_radius_decreases_with_more_pulses():
    r10 = uncertainty_radius(_make_identity(10))
    r50 = uncertainty_radius(_make_identity(50))
    r200 = uncertainty_radius(_make_identity(200))
    assert r10 > r50 > r200


def test_uncertainty_radius_positive():
    for n in [1, 5, 10, 100]:
        assert uncertainty_radius(_make_identity(n)) > 0
