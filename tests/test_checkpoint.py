import pytest
from unittest.mock import MagicMock, patch
from app.services.checkpoint import (
    derive_steward_key,
    get_valid_keys_for_steward,
    _derive_checkpoint_hash,
    GENESIS_HASH,
)


# --- derive_steward_key ---

def test_derive_steward_key_returns_pm_prefix():
    key = derive_steward_key("s1", oa=0.5, za=0.785, ta=1.0, checkpoint_hash="abc")
    assert key.startswith("pm_")


def test_derive_steward_key_deterministic():
    k1 = derive_steward_key("s1", 0.5, 0.785, 1.0, "abc")
    k2 = derive_steward_key("s1", 0.5, 0.785, 1.0, "abc")
    assert k1 == k2


def test_derive_steward_key_changes_with_checkpoint():
    k1 = derive_steward_key("s1", 0.5, 0.785, 1.0, "checkpoint_a")
    k2 = derive_steward_key("s1", 0.5, 0.785, 1.0, "checkpoint_b")
    assert k1 != k2


def test_derive_steward_key_changes_with_position():
    """Different OaZaTa positions produce different keys at the same checkpoint."""
    k1 = derive_steward_key("s1", oa=0.0, za=0.785, ta=1.0, checkpoint_hash="abc")
    k2 = derive_steward_key("s1", oa=0.9, za=0.785, ta=1.0, checkpoint_hash="abc")
    assert k1 != k2


def test_derive_steward_key_changes_with_steward_id():
    k1 = derive_steward_key("steward_a", 0.5, 0.785, 1.0, "abc")
    k2 = derive_steward_key("steward_b", 0.5, 0.785, 1.0, "abc")
    assert k1 != k2


def test_derive_steward_key_is_64_hex_chars():
    key = derive_steward_key("s1", 0.5, 0.785, 1.0, "abc")
    hex_part = key[3:]  # strip 'pm_'
    assert len(hex_part) == 64
    assert all(c in "0123456789abcdef" for c in hex_part)


# --- checkpoint hash chaining ---

def test_checkpoint_hash_deterministic():
    h1 = _derive_checkpoint_hash(1, "node_x", GENESIS_HASH, 1.0)
    h2 = _derive_checkpoint_hash(1, "node_x", GENESIS_HASH, 1.0)
    assert h1 == h2


def test_checkpoint_hash_changes_with_prev_hash():
    h1 = _derive_checkpoint_hash(1, "node_x", "prev_a", 1.0)
    h2 = _derive_checkpoint_hash(1, "node_x", "prev_b", 1.0)
    assert h1 != h2


def test_checkpoint_hash_changes_with_ta_ref():
    h1 = _derive_checkpoint_hash(1, "node_x", GENESIS_HASH, 1.0)
    h2 = _derive_checkpoint_hash(1, "node_x", GENESIS_HASH, 2.0)
    assert h1 != h2


# --- grace window ---

def test_grace_window_returns_multiple_keys():
    """
    With 3 checkpoints in DB and grace_window=2, should return 3 valid keys
    (current + 2 previous).
    """
    from app.models.checkpoint import Checkpoint

    cp0 = MagicMock(spec=Checkpoint); cp0.hash = "hash_0"
    cp1 = MagicMock(spec=Checkpoint); cp1.hash = "hash_1"
    cp2 = MagicMock(spec=Checkpoint); cp2.hash = "hash_2"

    mock_db = MagicMock()
    mock_query = mock_db.query.return_value
    mock_query.order_by.return_value.limit.return_value.all.return_value = [cp2, cp1, cp0]

    keys = get_valid_keys_for_steward("s1", 0.5, 0.785, 1.0, mock_db, grace_window=2)
    assert len(keys) == 3
    assert len(set(keys)) == 3  # all distinct


def test_grace_window_current_key_is_first():
    """The current checkpoint key is the first in the list."""
    from app.models.checkpoint import Checkpoint

    cp_current = MagicMock(spec=Checkpoint); cp_current.hash = "current_hash"
    mock_db = MagicMock()
    mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = [cp_current]

    keys = get_valid_keys_for_steward("s1", 0.5, 0.785, 1.0, mock_db, grace_window=0)
    assert len(keys) == 1
    assert keys[0] == derive_steward_key("s1", 0.5, 0.785, 1.0, "current_hash")
