"""
Integration test: advance_checkpoint() → emit_gossip() end-to-end.

Verifies that:
  1. A checkpoint advance triggers an outbound gossip emit to each
     registered peer.
  2. On successful delivery, peers.last_seen_checkpoint is updated.
  3. emit failure (network error) does NOT prevent the checkpoint
     from being committed — the advance still returns the new Checkpoint.
  4. No outbound GossipLog rows are written when there are no peers.
"""
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.checkpoint import Checkpoint
from app.models.peer import Peer
from app.models.gossip_log import GossipLog
from app.models.identity import OaZaTaIdentity
from app.services.checkpoint import advance_checkpoint


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _add_peer(db, peer_id, url):
    peer = Peer(peer_id=peer_id, url=url)
    db.add(peer)
    db.commit()
    return peer


class TestGossipEmitOnAdvance:
    def test_no_peers_advance_still_succeeds(self, db):
        """Checkpoint advances cleanly when there are no peers."""
        cp = advance_checkpoint(db, ta_ref=1.0)
        assert cp.index == 1
        assert cp.hash is not None
        # No outbound log rows
        assert db.query(GossipLog).filter_by(direction="outbound").count() == 0

    def test_emit_called_on_advance_with_peer(self, db):
        """Outbound GossipLog row created for a registered peer after advance."""
        _add_peer(db, "peer-emit-test", "http://peer-emit.local:8000")

        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.status_code = 200

        with patch("app.services.gossip.httpx.post", return_value=mock_resp):
            cp = advance_checkpoint(db, ta_ref=2.0)

        assert cp.index >= 1

        entry = (
            db.query(GossipLog)
            .filter_by(peer_id="peer-emit-test", direction="outbound")
            .order_by(GossipLog.id.desc())
            .first()
        )
        assert entry is not None
        assert entry.delivered is True
        assert entry.checkpoint_index == cp.index

    def test_last_seen_updated_after_successful_emit(self, db):
        """peers.last_seen_checkpoint is set after a successful emit."""
        peer = _add_peer(db, "peer-lastseen", "http://peer-ls.local:8000")
        assert peer.last_seen_checkpoint is None

        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.status_code = 200

        with patch("app.services.gossip.httpx.post", return_value=mock_resp):
            cp = advance_checkpoint(db, ta_ref=3.0)

        db.refresh(peer)
        assert peer.last_seen_checkpoint == cp.index
        assert peer.last_seen_at is not None

    def test_emit_failure_does_not_block_checkpoint(self, db):
        """A network error in gossip must not prevent the checkpoint from advancing."""
        _add_peer(db, "peer-fail", "http://peer-fail.local:8000")

        with patch("app.services.gossip.httpx.post", side_effect=Exception("refused")):
            cp = advance_checkpoint(db, ta_ref=4.0)

        # Checkpoint committed despite gossip failure
        assert cp.index >= 1
        stored = db.query(Checkpoint).filter_by(index=cp.index).first()
        assert stored is not None

        # Gossip failure is logged as delivered=False
        entry = (
            db.query(GossipLog)
            .filter_by(peer_id="peer-fail", direction="outbound")
            .order_by(GossipLog.id.desc())
            .first()
        )
        assert entry is not None
        assert entry.delivered is False

    def test_steward_positions_snapshot_passed_to_emit(self, db):
        """Steward (oa, za) positions are included in the gossip payload."""
        import uuid
        from app.models.steward import Steward

        # Create a steward + identity so steward_positions is non-empty
        sid = str(uuid.uuid4())
        db.add(Steward(id=sid, name="test-steward", trust_resource=0.0))
        db.flush()
        db.add(OaZaTaIdentity(
            id=str(uuid.uuid4()),
            steward_id=sid,
            oa=1.2,
            za=0.4,
            ta=0.0,
            api_key_hash="pm_dummy",
        ))
        db.commit()

        _add_peer(db, "peer-positions", "http://peer-pos.local:8000")

        captured = {}

        def capture_post(url, json, timeout):
            captured.update(json)
            r = MagicMock()
            r.is_success = True
            r.status_code = 200
            return r

        with patch("app.services.gossip.httpx.post", side_effect=capture_post):
            advance_checkpoint(db, ta_ref=5.0)

        # The gossip payload must contain q_cross and phi derived from the steward
        assert "q_cross" in captured
        assert "phi" in captured
        assert "checkpoint_hash" in captured
