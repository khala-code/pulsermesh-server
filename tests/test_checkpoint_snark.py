"""
tests/test_checkpoint_snark.py — integration tests for checkpoint → snark wiring

Verifies that advance_checkpoint() triggers snark updates and that
identity snark fields are written correctly for both empty and
populated pulse histories.
"""
import math
import uuid
import pytest
from app.services.checkpoint import advance_checkpoint
from app.services.domain import seed_domain_vectors
from app.models.identity import OaZaTaIdentity
from app.models.pulse import Pulse
from app.services.snark import MIN_CENTROID_PULSES


def _make_identity(db, steward_id: str, za: float = 0.0, ta: float = 5.0, mission_vector_za=None):
    identity = OaZaTaIdentity(
        id=str(uuid.uuid4()),
        steward_id=steward_id,
        oa=1.0,
        za=za,
        ta=ta,
        api_key_hash="testhash",
        mission_vector_za=mission_vector_za,
        pulse_count=0,
    )
    db.add(identity)
    db.commit()
    return identity


def _make_validated_pulse(db, steward_id: str, domain: str, value_add: float, checkpoint: int):
    p = Pulse(
        id=str(uuid.uuid4()),
        steward_id=steward_id,
        scarcity_domain=domain,
        description="test pulse",
        value_add=value_add,
        submitted_at_checkpoint=checkpoint,
        status="validated",
    )
    db.add(p)
    db.commit()
    return p


# ── tests ───────────────────────────────────────────────────────────────────

def test_advance_checkpoint_runs_without_identities(db):
    """Checkpoint advance must succeed even with no stewards registered."""
    seed_domain_vectors(db)
    cp = advance_checkpoint(db, ta_ref=1.0)
    assert cp.index == 1


def test_advance_checkpoint_snark_update_with_no_pulses(db):
    """Steward with no validated pulses: pulse_count=0, centroid=None after advance."""
    seed_domain_vectors(db)
    sid = str(uuid.uuid4())
    identity = _make_identity(db, sid)

    advance_checkpoint(db, ta_ref=1.0)

    db.refresh(identity)
    assert identity.pulse_count == 0
    assert identity.null_centroid_za is None
    assert identity.mission_delta is None


def test_advance_checkpoint_snark_update_below_min_pulses(db):
    """Steward with fewer than MIN_CENTROID_PULSES pulses: centroid stays None."""
    seed_domain_vectors(db)
    sid = str(uuid.uuid4())
    identity = _make_identity(db, sid)

    for i in range(MIN_CENTROID_PULSES - 1):
        _make_validated_pulse(db, sid, "water", 1.0, i + 1)

    advance_checkpoint(db, ta_ref=2.0)

    db.refresh(identity)
    assert identity.pulse_count == MIN_CENTROID_PULSES - 1
    assert identity.null_centroid_za is None


def test_advance_checkpoint_snark_sets_centroid_at_threshold(db):
    """Steward with exactly MIN_CENTROID_PULSES pulses: centroid is computed."""
    seed_domain_vectors(db)
    sid = str(uuid.uuid4())
    identity = _make_identity(db, sid)

    for i in range(MIN_CENTROID_PULSES):
        _make_validated_pulse(db, sid, "water", 1.0, i + 1)

    advance_checkpoint(db, ta_ref=3.0)

    db.refresh(identity)
    assert identity.pulse_count == MIN_CENTROID_PULSES
    assert identity.null_centroid_za is not None
    assert 0.0 <= identity.null_centroid_za < 2 * math.pi


def test_advance_checkpoint_mission_delta_computed_when_declared(db):
    """
    Steward with a declared mission_vector_za and enough pulses:
    mission_delta is set and within [0, pi].
    """
    seed_domain_vectors(db)
    sid = str(uuid.uuid4())
    # Declare mission vector at Za=0.5
    identity = _make_identity(db, sid, mission_vector_za=0.5)

    for i in range(MIN_CENTROID_PULSES):
        _make_validated_pulse(db, sid, "water", 1.0, i + 1)

    advance_checkpoint(db, ta_ref=4.0)

    db.refresh(identity)
    assert identity.mission_delta is not None
    assert 0.0 <= identity.mission_delta <= math.pi + 1e-9


def test_advance_checkpoint_mission_delta_none_without_declaration(db):
    """
    Steward with enough pulses but no declared mission_vector_za:
    mission_delta stays None.
    """
    seed_domain_vectors(db)
    sid = str(uuid.uuid4())
    identity = _make_identity(db, sid, mission_vector_za=None)

    for i in range(MIN_CENTROID_PULSES):
        _make_validated_pulse(db, sid, "water", 1.0, i + 1)

    advance_checkpoint(db, ta_ref=5.0)

    db.refresh(identity)
    assert identity.null_centroid_za is not None  # centroid computed
    assert identity.mission_delta is None          # but no vector to compare to


def test_advance_checkpoint_snark_failure_does_not_break_checkpoint(db):
    """
    If snark update raises for a steward, the checkpoint is still
    committed and returned correctly.
    """
    from unittest.mock import patch
    seed_domain_vectors(db)
    sid = str(uuid.uuid4())
    _make_identity(db, sid)

    with patch("app.services.snark.update_snark_identity", side_effect=RuntimeError("boom")):
        cp = advance_checkpoint(db, ta_ref=6.0)

    assert cp.index == 1  # checkpoint still advanced
