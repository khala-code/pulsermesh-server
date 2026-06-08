import math
from typing import Dict


# --- T_scarcity ---

def calculate_trust_delta(
    value_add: float,
    scarcity_domain: str,
    scarcity_weights: Dict[str, float],
    checkpoint_age: int = 0,
    decay_half_life: float = 4.0
) -> float:
    """
    Full trust pipeline (v1):

      trust_delta = T_decay · T_scarcity · value_add

    T_scarcity: domain weight scalar (innermost)
    T_decay:    exponential attenuation by checkpoint age (outer)

    checkpoint_age  - how many checkpoints old this pulse is at validation time.
                      0 = validated at the same checkpoint it was submitted.
    decay_half_life - number of checkpoints for trust to halve.
                      Default 4: a pulse validated 4 checkpoints late is worth 50%.
    """
    scarcity = _t_scarcity(value_add, scarcity_domain, scarcity_weights)
    decay = _t_decay(checkpoint_age, decay_half_life)
    return round(scarcity * decay, 8)


def _t_scarcity(value_add: float, domain: str, weights: Dict[str, float]) -> float:
    weight = weights.get(domain.lower(), weights.get("default", 1.0))
    return value_add * weight


def _t_decay(checkpoint_age: int, half_life: float) -> float:
    """
    T_decay scalar: exp(-ln(2) / half_life * age)

    age=0           → 1.0   (no attenuation)
    age=half_life   → 0.5   (half value)
    age=2*half_life → 0.25  (quarter value)

    Uses natural exponential so it composes cleanly when
    T_proximity is added as the next left-multiply.
    """
    if checkpoint_age <= 0:
        return 1.0
    return math.exp(-math.log(2) / half_life * checkpoint_age)


# --- Matrix scaffolds ---

def build_scarcity_matrix(scarcity_weights: Dict[str, float], domains: list[str]) -> list[list[float]]:
    """
    Explicit T_scarcity diagonal matrix for a given domain ordering.
    Off-diagonal entries = 0 (cross-coupling is a v2 concern).
    """
    n = len(domains)
    matrix = [[0.0] * n for _ in range(n)]
    for i, domain in enumerate(domains):
        matrix[i][i] = scarcity_weights.get(domain, scarcity_weights.get("default", 1.0))
    return matrix


def build_decay_matrix(checkpoint_age: int, half_life: float, n: int) -> list[list[float]]:
    """
    Explicit T_decay scalar-identity matrix (same decay applied to all domains).
    Returns scalar * I_n. Composes with T_scarcity as T_decay @ T_scarcity.
    """
    scalar = _t_decay(checkpoint_age, half_life)
    return [[scalar if i == j else 0.0 for j in range(n)] for i in range(n)]
