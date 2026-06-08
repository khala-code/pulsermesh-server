import pytest
from app.services.trust import calculate_trust_delta, build_scarcity_matrix
from app.config import DEFAULT_SCARCITY_WEIGHTS


# --- calculate_trust_delta ---

def test_water_domain_applies_weight():
    delta = calculate_trust_delta(1.0, "water", DEFAULT_SCARCITY_WEIGHTS)
    assert delta == 1.8


def test_food_domain_applies_weight():
    delta = calculate_trust_delta(2.0, "food", DEFAULT_SCARCITY_WEIGHTS)
    assert delta == 3.0


def test_energy_domain_applies_weight():
    delta = calculate_trust_delta(10.0, "energy", DEFAULT_SCARCITY_WEIGHTS)
    assert delta == 12.0


def test_shelter_domain_applies_weight():
    delta = calculate_trust_delta(1.0, "shelter", DEFAULT_SCARCITY_WEIGHTS)
    assert delta == 1.4


def test_unknown_domain_uses_default_weight():
    delta = calculate_trust_delta(5.0, "moonbeams", DEFAULT_SCARCITY_WEIGHTS)
    assert delta == 5.0  # default weight = 1.0


def test_domain_lookup_is_case_insensitive():
    delta_lower = calculate_trust_delta(1.0, "water", DEFAULT_SCARCITY_WEIGHTS)
    delta_upper = calculate_trust_delta(1.0, "WATER", DEFAULT_SCARCITY_WEIGHTS)
    assert delta_lower == delta_upper


def test_negative_value_add_decrements_trust():
    """Negative pulses are valid — trust can be decremented."""
    delta = calculate_trust_delta(-2.0, "water", DEFAULT_SCARCITY_WEIGHTS)
    assert delta == -3.6


def test_zero_value_add_returns_zero():
    delta = calculate_trust_delta(0.0, "water", DEFAULT_SCARCITY_WEIGHTS)
    assert delta == 0.0


def test_custom_weight_override():
    custom = {**DEFAULT_SCARCITY_WEIGHTS, "water": 3.0}
    delta = calculate_trust_delta(2.0, "water", custom)
    assert delta == 6.0


def test_original_shed_alpha_pulse():
    """Regression: Shed Node Alpha's first pulse (value_add=3.5, water)
    should now produce 3.5 * 1.8 = 6.3, not 3.5."""
    delta = calculate_trust_delta(3.5, "water", DEFAULT_SCARCITY_WEIGHTS)
    assert delta == pytest.approx(6.3)


# --- build_scarcity_matrix ---

def test_scarcity_matrix_is_diagonal():
    domains = ["water", "food", "energy"]
    M = build_scarcity_matrix(DEFAULT_SCARCITY_WEIGHTS, domains)
    assert M[0][0] == 1.8  # water
    assert M[1][1] == 1.5  # food
    assert M[2][2] == 1.2  # energy
    # off-diagonal zeros
    assert M[0][1] == 0.0
    assert M[1][0] == 0.0


def test_scarcity_matrix_shape():
    domains = ["water", "food", "energy", "shelter"]
    M = build_scarcity_matrix(DEFAULT_SCARCITY_WEIGHTS, domains)
    assert len(M) == 4
    assert all(len(row) == 4 for row in M)


def test_scarcity_matrix_unknown_domain_uses_default():
    domains = ["water", "moonbeams"]
    M = build_scarcity_matrix(DEFAULT_SCARCITY_WEIGHTS, domains)
    assert M[1][1] == 1.0  # default
