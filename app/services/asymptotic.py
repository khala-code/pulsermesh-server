"""
app/services/asymptotic.py — Asymptotic Authentication Computations

Implements the observable wavefunction model from docs/asymptotic-auth.md.

Key quantities computed here:
  - Uncertainty band   ΔΨ(n) ~ (1/√n) · exp(-λ · Ta)   (§ 3)
  - Phase lag signal   q_s = Ωa · sin(ΔZa)               (§ 5)
  - Node quadrature    Q_node = Σ q_s                      (§ 6)
  - Order parameter    Φ = |Σ Ωa · exp(i·Za)|             (§ 7)
  - Flywheel δZa       (value_add · w) / |Ωa|              (§ 2)
  - Coherence score    cos(ΔZa)                            (§ 5)

None of these functions write to the database; they are pure computations
intended to be called by validation, checkpoint-advance, and dividend
weighting code.
"""
import math
from typing import Sequence


# ── uncertainty band (§ 3) ──────────────────────────────────────────

def uncertainty_band(n: int, ta: float, lam: float = 0.1) -> float:
    """
    ΔΨ(n) ~ (1 / √n) · exp(-λ · Ta)

    n   — number of validated pulses for this steward.
    ta  — geodesic arc length (maturity); the Ta coordinate.
    lam — longitudinal decay constant λ.  Tunable; default 0.1.

    Returns 1.0 when n == 0 (maximum uncertainty before any pulses).
    The band is dimensionless; interpret it as the relative spread of
    the uncertainty window around the steward's current position.
    """
    if n <= 0:
        return 1.0
    return (1.0 / math.sqrt(n)) * math.exp(-lam * ta)


# ── complex inner product channels (§ 5) ───────────────────────────

def real_coupling(oa: float, za_steward: float, za_node: float) -> float:
    """
    Real channel: Re(<Ψ_s | Ψ_n>) = Ωa · cos(ΔZa)

    This is T_proximity as already implemented in trust.py.
    Provided here for symmetry with phase_lag_signal() and to serve
    as the canonical reference for the coupling formula.
    """
    return oa * math.cos(za_steward - za_node)


def phase_lag_signal(oa: float, za_steward: float, za_node: float) -> float:
    """
    Imaginary channel: q_s = Im(<Ψ_s | Ψ_n>) = Ωa · sin(ΔZa)

    Positive q_s  → steward lags the node (reactive)
    Negative q_s  → steward leads the node (anticipatory)
    |q_s| large with Re ≈ 0  → scout: near-orthogonal, pure phase signal
    """
    return oa * math.sin(za_steward - za_node)


def coherence_score(za_steward: float, za_node: float) -> float:
    """
    coherence_s = cos(ΔZa)

    1.0   → perfectly coherent, fully constructive
    0.0   → scout (quadrature, pure imaginary channel)
    -1.0  → fully anti-aligned, destructive
    """
    return math.cos(za_steward - za_node)


# ── node PLL aggregate (§ 6) ────────────────────────────────────────

def node_quadrature_aggregate(
    stewards: Sequence[tuple[float, float]],
    za_node: float
) -> float:
    """
    Q_node = Σ_s  Ωa_s · sin(Za_s - Za_n)

    stewards — sequence of (oa, za) pairs for all active stewards.
    za_node  — the node's current Za reference.

    Q_node is the PLL error signal:
      Q = 0   → locked; node is at the resonant frequency of its population
      Q > 0   → stewards systematically lag; slow node Za rotation
      Q < 0   → stewards systematically lead; accelerate node Za rotation
    """
    return sum(
        phase_lag_signal(oa, za, za_node)
        for oa, za in stewards
    )


def node_za_update(za_node: float, q_node: float, kappa: float = 0.01) -> float:
    """
    Apply one PLL step: dZa_n/dt = -κ · Q_node

    za_node  — current node Za
    q_node   — quadrature aggregate from node_quadrature_aggregate()
    kappa    — tuning rate; small values give slow/stable lock,
               large values give fast lock but potential oscillation.

    Returns the updated Za_n.  Call at each checkpoint advance.
    """
    return za_node - kappa * q_node


# ── mesh order parameter (§ 7) ───────────────────────────────────────

def order_parameter(
    stewards: Sequence[tuple[float, float]]
) -> float:
    """
    Φ = | Σ_s  Ωa_s · exp(i · Za_s) |

    stewards — sequence of (oa, za) pairs.

    Φ = 0  → fully symmetric, no dominant phase; disordered mesh
    Φ > 0  → broken symmetry, dominant phase has emerged; ordered mesh

    This is the mesh's measure of economic coherence (§ 7).
    """
    re = sum(oa * math.cos(za) for oa, za in stewards)
    im = sum(oa * math.sin(za) for oa, za in stewards)
    return math.sqrt(re ** 2 + im ** 2)


# ── flywheel δZa (§ 2) ──────────────────────────────────────────────

def flywheel_delta_za(
    value_add: float,
    domain_weight: float,
    oa: float,
    min_oa: float = 0.01
) -> float:
    """
    δZa = (value_add · w(domain)) / |Ωa|

    The Za rotation per pulse is attenuated by the steward's current
    orbit amplitude.  A thick-spiral (mature) steward rotates less per
    pulse than a thin-spiral (new) steward — the flywheel property.

    min_oa guards against division by zero for brand-new stewards.
    """
    effective_oa = max(abs(oa), min_oa)
    return (value_add * domain_weight) / effective_oa


# ── uncertainty band as auth confidence (§ 8 / identity.py bridge) ───

def is_within_band(
    candidate_za: float,
    authentic_za: float,
    band: float
) -> bool:
    """
    Return True if candidate_za falls within the uncertainty band
    of the authentic Za position.

    Used by trajectory witness logic: a rival trajectory must fall
    outside this band after witness revelation to be evicted.
    """
    delta = abs(candidate_za - authentic_za) % (2 * math.pi)
    # Wrap to [-π, π]
    if delta > math.pi:
        delta = 2 * math.pi - delta
    return delta <= band
