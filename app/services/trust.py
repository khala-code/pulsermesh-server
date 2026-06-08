import math
from typing import Dict


# Minimum proximity threshold.
# Pulses from stewards in destructive interference are rejected at validation.
# Below this value the spiral coupling is too weak to accrue trust.
PROXIMITY_FLOOR = -1.0  # allow full destructive range (let the geometry decide)


def calculate_trust_delta(
    value_add: float,
    scarcity_domain: str,
    scarcity_weights: Dict[str, float],
    checkpoint_age: int = 0,
    decay_half_life: float = 4.0,
    steward_oa: float = 1.0,
    steward_za: float = 0.0,
    node_za: float = 0.0,
) -> float:
    """
    Full trust pipeline (v1):

      trust_delta = T_proximity · T_decay · T_scarcity · value_add

    T_scarcity:  domain weight scalar (innermost)
    T_decay:     exponential attenuation by checkpoint age
    T_proximity: zeta spiral phase coupling (outermost)

    Proximity = Oa_steward × cos(za_steward - za_node)
    - Aligned spirals (delta_za=0):        proximity = Oa  (constructive)
    - Quarter phase (delta_za=pi/2):       proximity = 0   (orthogonal, no coupling)
    - Anti-aligned (delta_za=pi):          proximity = -Oa (destructive)

    Negative trust_delta from destructive interference is valid —
    the geometry can decrement trust. The validation layer may choose
    to reject pulses below a proximity threshold.
    """
    scarcity = _t_scarcity(value_add, scarcity_domain, scarcity_weights)
    decay = _t_decay(checkpoint_age, decay_half_life)
    proximity = _t_proximity(steward_oa, steward_za, node_za)
    return round(scarcity * decay * proximity, 8)


def _t_scarcity(value_add: float, domain: str, weights: Dict[str, float]) -> float:
    weight = weights.get(domain.lower(), weights.get("default", 1.0))
    return value_add * weight


def _t_decay(checkpoint_age: int, half_life: float) -> float:
    """
    exp(-ln(2) / half_life * age)
    age=0 → 1.0, age=half_life → 0.5, age=2*half_life → 0.25
    """
    if checkpoint_age <= 0:
        return 1.0
    return math.exp(-math.log(2) / half_life * checkpoint_age)


def _t_proximity(oa: float, za_steward: float, za_node: float) -> float:
    """
    T_proximity scalar: Oa × cos(za_steward - za_node)

    Oa (omega) is the thickness of the steward's critical line —
    it modulates the amplitude of the interference pattern.
    A steward with Oa=0.5 has half the coupling amplitude of one with Oa=1.0
    regardless of phase alignment.

    Za difference is the phase offset between the steward's spiral
    and the node's reference wave. Full constructive at delta=0,
    full destructive at delta=pi.
    """
    delta_za = za_steward - za_node
    return oa * math.cos(delta_za)


# --- Matrix scaffolds ---

def build_scarcity_matrix(scarcity_weights: Dict[str, float], domains: list[str]) -> list[list[float]]:
    n = len(domains)
    matrix = [[0.0] * n for _ in range(n)]
    for i, domain in enumerate(domains):
        matrix[i][i] = scarcity_weights.get(domain, scarcity_weights.get("default", 1.0))
    return matrix


def build_decay_matrix(checkpoint_age: int, half_life: float, n: int) -> list[list[float]]:
    scalar = _t_decay(checkpoint_age, half_life)
    return [[scalar if i == j else 0.0 for j in range(n)] for i in range(n)]


def build_proximity_matrix(oa: float, za_steward: float, za_node: float, n: int) -> list[list[float]]:
    """
    T_proximity as scalar-identity matrix.
    Same proximity scalar applied to all domain components.
    Off-diagonal coupling (domain cross-proximity) is a v2 concern.
    """
    scalar = _t_proximity(oa, za_steward, za_node)
    return [[scalar if i == j else 0.0 for j in range(n)] for i in range(n)]
