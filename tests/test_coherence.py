import pytest
from unittest.mock import MagicMock, patch
from app.services.coherence import update_coherence, MIN_TRIANGULATIONS
from app.models.steward import Steward
from app.models.identity import OaZaTaIdentity


def _make_steward(steward_id="s1"):
    s = MagicMock(spec=Steward)
    s.id = steward_id
    s.coherence_score = 0.0
    return s


def _make_identity(steward_id="s1", variance=None, count=0):
    i = MagicMock(spec=OaZaTaIdentity)
    i.steward_id = steward_id
    i.position_variance = variance
    i.triangulation_count = count
    return i


def _make_db(steward, identity):
    db = MagicMock()
    def query_side_effect(model):
        q = MagicMock()
        if model == Steward:
            q.filter.return_value.first.return_value = steward
        elif model == OaZaTaIdentity:
            q.filter.return_value.first.return_value = identity
        return q
    db.query.side_effect = query_side_effect
    return db


def test_coherence_zero_when_no_triangulations():
    db = _make_db(_make_steward(), _make_identity(count=0))
    score = update_coherence(db, "s1")
    assert score == 0.0


def test_coherence_zero_below_min_triangulations():
    db = _make_db(_make_steward(), _make_identity(count=MIN_TRIANGULATIONS - 1))
    score = update_coherence(db, "s1")
    assert score == 0.0


def test_coherence_zero_when_variance_is_none():
    db = _make_db(_make_steward(), _make_identity(variance=None, count=MIN_TRIANGULATIONS))
    score = update_coherence(db, "s1")
    assert score == 0.0


def test_coherence_one_when_variance_zero():
    """Perfect spiral stability → coherence = 1.0"""
    db = _make_db(_make_steward(), _make_identity(variance=0.0, count=MIN_TRIANGULATIONS))
    score = update_coherence(db, "s1")
    assert score == 1.0


def test_coherence_half_when_variance_one():
    """variance=1 → coherence = 1/(1+1) = 0.5"""
    db = _make_db(_make_steward(), _make_identity(variance=1.0, count=MIN_TRIANGULATIONS))
    score = update_coherence(db, "s1")
    assert abs(score - 0.5) < 1e-6


def test_coherence_decreases_with_variance():
    """Higher variance → lower coherence."""
    db_low = _make_db(_make_steward(), _make_identity(variance=0.1, count=MIN_TRIANGULATIONS))
    db_high = _make_db(_make_steward(), _make_identity(variance=5.0, count=MIN_TRIANGULATIONS))
    score_low = update_coherence(db_low, "s1")
    score_high = update_coherence(db_high, "s1")
    assert score_low > score_high


def test_coherence_returns_zero_when_steward_not_found():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    score = update_coherence(db, "nonexistent")
    assert score == 0.0


def test_coherence_score_is_between_zero_and_one():
    for variance in [0.0, 0.1, 1.0, 10.0, 100.0]:
        db = _make_db(_make_steward(), _make_identity(variance=variance, count=MIN_TRIANGULATIONS))
        score = update_coherence(db, "s1")
        assert 0.0 <= score <= 1.0
