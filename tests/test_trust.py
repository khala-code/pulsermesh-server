import math
import pytest
from app.services.trust import (
    calculate_trust_delta, build_scarcity_matrix, build_decay_matrix,
    build_proximity_matrix, _t_decay, _t_proximity
)
from app.config import DEFAULT_SCARCITY_WEIGHTS


# --- T_scarcity ---

def test_water_domain_applies_weight():
    assert calculate_trust_delta(1.0, "water", DEFAULT_SCARCITY_WEIGHTS) == 1.8

def test_food_domain_applies_weight():
    assert calculate_trust_delta(2.0, "food", DEFAULT_SCARCITY_WEIGHTS) == 3.0

def test_unknown_domain_uses_default_weight():
    assert calculate_trust_delta(5.0, "moonbeams", DEFAULT_SCARCITY_WEIGHTS) == 5.0

def test_domain_lookup_is_case_insensitive():
    assert calculate_trust_delta(1.0, "water", DEFAULT_SCARCITY_WEIGHTS) == \
           calculate_trust_delta(1.0, "WATER", DEFAULT_SCARCITY_WEIGHTS)

def test_negative_value_add_decrements_trust():
    assert calculate_trust_delta(-2.0, "water", DEFAULT_SCARCITY_WEIGHTS) == pytest.approx(-3.6)

def test_zero_value_add_returns_zero():
    assert calculate_trust_delta(0.0, "water", DEFAULT_SCARCITY_WEIGHTS) == 0.0


# --- T_decay ---

def test_decay_age_zero_is_one():
    assert _t_decay(0, 4.0) == 1.0

def test_decay_at_half_life_is_half():
    assert _t_decay(4, 4.0) == pytest.approx(0.5, rel=1e-6)

def test_decay_at_double_half_life_is_quarter():
    assert _t_decay(8, 4.0) == pytest.approx(0.25, rel=1e-6)

def test_decay_is_monotonically_decreasing():
    values = [_t_decay(age, 4.0) for age in range(10)]
    assert all(values[i] > values[i+1] for i in range(len(values)-1))

def test_decay_never_reaches_zero():
    assert _t_decay(1000, 4.0) > 0.0

def test_decay_negative_age_returns_one():
    assert _t_decay(-1, 4.0) == 1.0


# --- T_proximity ---

def test_proximity_aligned_spirals_is_oa():
    """delta_za=0 → cos(0)=1.0 → proximity=Oa"""
    assert _t_proximity(oa=1.0, za_steward=0.0, za_node=0.0) == pytest.approx(1.0)

def test_proximity_anti_aligned_is_negative_oa():
    """delta_za=pi → cos(pi)=-1.0 → proximity=-Oa (destructive)"""
    assert _t_proximity(oa=1.0, za_steward=math.pi, za_node=0.0) == pytest.approx(-1.0)

def test_proximity_quarter_phase_is_zero():
    """delta_za=pi/2 → cos(pi/2)=0.0 → orthogonal, no coupling"""
    assert _t_proximity(oa=1.0, za_steward=math.pi/2, za_node=0.0) == pytest.approx(0.0, abs=1e-10)

def test_proximity_oa_scales_amplitude():
    """Oa=0.5 gives half the coupling amplitude of Oa=1.0"""
    p1 = _t_proximity(oa=1.0, za_steward=0.5, za_node=0.0)
    p2 = _t_proximity(oa=0.5, za_steward=0.5, za_node=0.0)
    assert p2 == pytest.approx(p1 * 0.5)

def test_proximity_node_za_offset_shifts_phase():
    """Proximity is symmetric: steward at za=X relative to node at za=X is aligned."""
    p = _t_proximity(oa=1.0, za_steward=1.0, za_node=1.0)
    assert p == pytest.approx(1.0)

def test_proximity_constructive_positive_trust():
    p = _t_proximity(oa=1.0, za_steward=0.1, za_node=0.0)
    assert p > 0

def test_proximity_destructive_negative_trust():
    p = _t_proximity(oa=1.0, za_steward=math.pi + 0.1, za_node=0.0)
    assert p < 0


# --- Full pipeline ---

def test_pipeline_full_constructive():
    """Aligned spiral, age=0, water: 3.5 * 1.8 * 1.0 * 1.0 = 6.3"""
    delta = calculate_trust_delta(
        value_add=3.5, scarcity_domain="water",
        scarcity_weights=DEFAULT_SCARCITY_WEIGHTS,
        checkpoint_age=0, steward_oa=1.0, steward_za=0.0, node_za=0.0
    )
    assert delta == pytest.approx(6.3)

def test_pipeline_attenuates_with_age():
    fresh = calculate_trust_delta(1.0, "water", DEFAULT_SCARCITY_WEIGHTS, checkpoint_age=0)
    stale = calculate_trust_delta(1.0, "water", DEFAULT_SCARCITY_WEIGHTS, checkpoint_age=4)
    assert stale == pytest.approx(fresh * 0.5, rel=1e-6)

def test_pipeline_destructive_interference_decrements_trust():
    """Anti-aligned steward (za=pi) produces negative trust delta."""
    delta = calculate_trust_delta(
        value_add=1.0, scarcity_domain="water",
        scarcity_weights=DEFAULT_SCARCITY_WEIGHTS,
        steward_oa=1.0, steward_za=math.pi, node_za=0.0
    )
    assert delta < 0

def test_pipeline_orthogonal_produces_zero_trust():
    """Quarter-phase steward produces no trust accrual."""
    delta = calculate_trust_delta(
        value_add=1.0, scarcity_domain="water",
        scarcity_weights=DEFAULT_SCARCITY_WEIGHTS,
        steward_oa=1.0, steward_za=math.pi/2, node_za=0.0
    )
    assert delta == pytest.approx(0.0, abs=1e-10)

def test_pipeline_high_oa_amplifies_trust():
    """Higher Oa (thicker spiral) gives proportionally more trust."""
    d1 = calculate_trust_delta(1.0, "water", DEFAULT_SCARCITY_WEIGHTS, steward_oa=1.0, steward_za=0.0, node_za=0.0)
    d2 = calculate_trust_delta(1.0, "water", DEFAULT_SCARCITY_WEIGHTS, steward_oa=2.0, steward_za=0.0, node_za=0.0)
    assert d2 == pytest.approx(d1 * 2.0)


# --- Matrix scaffolds ---

def test_scarcity_matrix_is_diagonal():
    M = build_scarcity_matrix(DEFAULT_SCARCITY_WEIGHTS, ["water", "food", "energy"])
    assert M[0][0] == 1.8
    assert M[0][1] == 0.0

def test_decay_matrix_is_scalar_identity():
    M = build_decay_matrix(4, 4.0, 3)
    for i in range(3):
        assert M[i][i] == pytest.approx(0.5)

def test_proximity_matrix_is_scalar_identity():
    M = build_proximity_matrix(1.0, 0.0, 0.0, 3)
    for i in range(3):
        assert M[i][i] == pytest.approx(1.0)
        for j in range(3):
            if i != j:
                assert M[i][j] == 0.0
