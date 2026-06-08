import math
import pytest
from app.services.trust import calculate_trust_delta, build_scarcity_matrix, build_decay_matrix, _t_decay
from app.config import DEFAULT_SCARCITY_WEIGHTS


# --- T_scarcity ---

def test_water_domain_applies_weight():
    assert calculate_trust_delta(1.0, "water", DEFAULT_SCARCITY_WEIGHTS) == 1.8

def test_food_domain_applies_weight():
    assert calculate_trust_delta(2.0, "food", DEFAULT_SCARCITY_WEIGHTS) == 3.0

def test_energy_domain_applies_weight():
    assert calculate_trust_delta(10.0, "energy", DEFAULT_SCARCITY_WEIGHTS) == 12.0

def test_shelter_domain_applies_weight():
    assert calculate_trust_delta(1.0, "shelter", DEFAULT_SCARCITY_WEIGHTS) == 1.4

def test_unknown_domain_uses_default_weight():
    assert calculate_trust_delta(5.0, "moonbeams", DEFAULT_SCARCITY_WEIGHTS) == 5.0

def test_domain_lookup_is_case_insensitive():
    assert calculate_trust_delta(1.0, "water", DEFAULT_SCARCITY_WEIGHTS) == \
           calculate_trust_delta(1.0, "WATER", DEFAULT_SCARCITY_WEIGHTS)

def test_negative_value_add_decrements_trust():
    assert calculate_trust_delta(-2.0, "water", DEFAULT_SCARCITY_WEIGHTS) == pytest.approx(-3.6)

def test_zero_value_add_returns_zero():
    assert calculate_trust_delta(0.0, "water", DEFAULT_SCARCITY_WEIGHTS) == 0.0

def test_custom_weight_override():
    custom = {**DEFAULT_SCARCITY_WEIGHTS, "water": 3.0}
    assert calculate_trust_delta(2.0, "water", custom) == 6.0

def test_original_shed_alpha_pulse():
    """Regression: value_add=3.5, water, age=0 → 3.5 * 1.8 * 1.0 = 6.3"""
    assert calculate_trust_delta(3.5, "water", DEFAULT_SCARCITY_WEIGHTS, checkpoint_age=0) == pytest.approx(6.3)


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
    """Negative age (validated before submission checkpoint) clamps to 1.0."""
    assert _t_decay(-1, 4.0) == 1.0


# --- Combined pipeline ---

def test_pipeline_age_zero_equals_scarcity_only():
    """At age=0, decay=1.0 so result equals pure T_scarcity."""
    delta = calculate_trust_delta(1.0, "water", DEFAULT_SCARCITY_WEIGHTS, checkpoint_age=0)
    assert delta == pytest.approx(1.8)

def test_pipeline_attenuates_with_age():
    fresh = calculate_trust_delta(1.0, "water", DEFAULT_SCARCITY_WEIGHTS, checkpoint_age=0)
    stale = calculate_trust_delta(1.0, "water", DEFAULT_SCARCITY_WEIGHTS, checkpoint_age=4)
    assert stale == pytest.approx(fresh * 0.5, rel=1e-6)

def test_pipeline_water_pulse_at_half_life():
    """water pulse value_add=3.5, age=4 (half life) → 3.5 * 1.8 * 0.5 = 3.15"""
    delta = calculate_trust_delta(3.5, "water", DEFAULT_SCARCITY_WEIGHTS, checkpoint_age=4)
    assert delta == pytest.approx(3.15, rel=1e-6)


# --- Matrix scaffolds ---

def test_scarcity_matrix_is_diagonal():
    M = build_scarcity_matrix(DEFAULT_SCARCITY_WEIGHTS, ["water", "food", "energy"])
    assert M[0][0] == 1.8
    assert M[1][1] == 1.5
    assert M[2][2] == 1.2
    assert M[0][1] == 0.0

def test_decay_matrix_is_scalar_identity():
    M = build_decay_matrix(4, 4.0, 3)
    for i in range(3):
        assert M[i][i] == pytest.approx(0.5)
        for j in range(3):
            if i != j:
                assert M[i][j] == 0.0

def test_scarcity_matrix_unknown_domain_uses_default():
    M = build_scarcity_matrix(DEFAULT_SCARCITY_WEIGHTS, ["water", "moonbeams"])
    assert M[1][1] == 1.0
