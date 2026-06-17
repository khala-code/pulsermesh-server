"""
tests/test_domain.py — domain vector service tests
"""
import math
import pytest
from unittest.mock import patch
from app.services.domain import (
    seed_domain_vectors,
    get_domain_za,
    resolve_mission_vector,
)
from app.config import DEFAULT_SCARCITY_WEIGHTS


# ── seeding ───────────────────────────────────────────────────────────────────

def test_seed_creates_one_vector_per_domain(db):
    created = seed_domain_vectors(db)
    domain_names = {dv.domain for dv in created}
    expected = set(DEFAULT_SCARCITY_WEIGHTS.keys())
    assert domain_names == expected


def test_seed_za_values_are_in_range(db):
    seed_domain_vectors(db)
    from app.models.domain_vector import DomainVector
    vectors = db.query(DomainVector).all()
    for dv in vectors:
        assert 0.0 <= dv.za < 2 * math.pi, f"{dv.domain} za={dv.za} out of range"


def test_seed_is_idempotent(db):
    first = seed_domain_vectors(db)
    second = seed_domain_vectors(db)
    # Second call should create nothing new
    assert len(second) == 0
    from app.models.domain_vector import DomainVector
    total = db.query(DomainVector).count()
    assert total == len(DEFAULT_SCARCITY_WEIGHTS)


def test_seed_za_values_are_evenly_spaced(db):
    seed_domain_vectors(db)
    from app.models.domain_vector import DomainVector
    from app.config import settings
    directional = [
        dv for dv in db.query(DomainVector)
        .filter(DomainVector.node_id == settings.node_id)
        .all()
        if dv.domain != "default"
    ]
    n = len(directional)
    expected_step = (2 * math.pi) / n
    za_values = sorted(dv.za for dv in directional)
    for i in range(len(za_values) - 1):
        gap = za_values[i + 1] - za_values[i]
        assert abs(gap - expected_step) < 1e-4, f"uneven spacing at index {i}: gap={gap}"


# ── lookup ─────────────────────────────────────────────────────────────────────

def test_get_domain_za_returns_correct_value(db):
    seed_domain_vectors(db)
    za = get_domain_za(db, "water")
    assert isinstance(za, float)
    assert 0.0 <= za < 2 * math.pi


def test_get_domain_za_unknown_falls_back_to_default(db):
    seed_domain_vectors(db)
    default_za = get_domain_za(db, "default")
    unknown_za = get_domain_za(db, "nonexistent_domain")
    assert unknown_za == default_za


def test_get_domain_za_case_insensitive(db):
    seed_domain_vectors(db)
    za_lower = get_domain_za(db, "water")
    za_upper = get_domain_za(db, "WATER")
    assert za_lower == za_upper


# ── mission vector resolution ────────────────────────────────────────────────

def test_resolve_single_domain_returns_its_za(db):
    seed_domain_vectors(db)
    water_za = get_domain_za(db, "water")
    resolved = resolve_mission_vector(db, ["water"])
    assert abs(resolved - water_za) < 1e-6


def test_resolve_empty_domains_returns_zero(db):
    seed_domain_vectors(db)
    resolved = resolve_mission_vector(db, [])
    assert resolved == 0.0


def test_resolve_returns_value_in_range(db):
    seed_domain_vectors(db)
    resolved = resolve_mission_vector(db, ["water", "energy", "food"])
    assert 0.0 <= resolved < 2 * math.pi


def test_resolve_unknown_domains_returns_fallback(db):
    seed_domain_vectors(db)
    resolved = resolve_mission_vector(db, ["unknown_domain_xyz"])
    # Falls back to default domain Za
    default_za = get_domain_za(db, "default")
    assert abs(resolved - default_za) < 1e-6
