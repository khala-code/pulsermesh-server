from typing import Dict


def calculate_trust_delta(
    value_add: float,
    scarcity_domain: str,
    scarcity_weights: Dict[str, float]
) -> float:
    """
    T_scarcity transform — the innermost matrix in the trust pipeline.

    trust_delta = T_scarcity(domain) · value_add

    T_scarcity is a diagonal matrix in domain-space; for a single domain
    pulse this reduces to a scalar multiplication by the domain weight.

    The full pipeline will be:
      trust_delta = T_proximity · T_decay · T_scarcity · value_add

    Unknown domains fall back to the 'default' weight.
    Negative value_add is valid (trust can be decremented by a negative pulse).
    """
    weight = scarcity_weights.get(scarcity_domain.lower(), scarcity_weights.get("default", 1.0))
    return round(value_add * weight, 8)


def build_scarcity_matrix(scarcity_weights: Dict[str, float], domains: list[str]) -> list[list[float]]:
    """
    Build the explicit T_scarcity diagonal matrix for a given domain ordering.
    Unused today but scaffolds the full matrix multiply pipeline.

    Returns an NxN diagonal matrix where M[i][i] = weight for domains[i].
    Off-diagonal entries are 0 (no cross-coupling in v1).
    """
    n = len(domains)
    matrix = [[0.0] * n for _ in range(n)]
    for i, domain in enumerate(domains):
        matrix[i][i] = scarcity_weights.get(domain, scarcity_weights.get("default", 1.0))
    return matrix
