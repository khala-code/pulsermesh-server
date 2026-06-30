"""
Unit tests for app/services/gossip.py.

All tests use an in-memory SQLite database and mock httpx.post so
no real network calls are made.
"""
import math
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.peer import Peer
from app.models.gossip_log import GossipLog
from app.schemas.gossip import NodeGossip
from app.services import gossip as gossip_svc
from app.config import settings


@pytest.fixture(scope="module")
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def make_gossip(**kwargs) -> NodeGossip:
    defaults = dict(
        node_id="peer-node-abc",
        checkpoint_index=1,
        checkpoint_hash="deadbeef" * 8,
        za=0.3,
        omega_a=1.0,
        q_cross=0.1,
        phi=0.8,
        ta_ref=1.0,
    )
    defaults.update(kwargs)
    return NodeGossip(**defaults)


# ===========================================================================
# assemble_node_gossip
# ===========================================================================

class TestAssembleNodeGossip:
    def test_returns_node_gossip_schema(self):
        gossip = gossip_svc.assemble_node_gossip(
            checkpoint_index=3,
            checkpoint_hash="abc" * 21 + "a",
            ta_ref=2.5,
            steward_positions=[(1.0, 0.1), (1.2, 0.5)],
        )
        assert isinstance(gossip, NodeGossip)
        assert gossip.checkpoint_index == 3
        assert gossip.ta_ref == 2.5
        assert gossip.node_id == settings.node_id

    def test_q_cross_zero_for_empty_stewards(self):
        gossip = gossip_svc.assemble_node_gossip(
            checkpoint_index=1,
            checkpoint_hash="0" * 64,
            ta_ref=0.0,
            steward_positions=[],
        )
        assert gossip.q_cross == 0.0
        assert gossip.phi == 0.0

    def test_q_cross_is_aggregate(self):
        # Single steward at za=node_za → sin(0)=0, Q_cross should be 0
        gossip = gossip_svc.assemble_node_gossip(
            checkpoint_index=1,
            checkpoint_hash="0" * 64,
            ta_ref=0.0,
            steward_positions=[(1.0, settings.node_za)],
        )
        assert gossip.q_cross == pytest.approx(0.0, abs=1e-9)

    def test_phi_nonzero_for_aligned_stewards(self):
        # Two stewards at same za → phi = sum(oa) > 0
        gossip = gossip_svc.assemble_node_gossip(
            checkpoint_index=1,
            checkpoint_hash="0" * 64,
            ta_ref=0.0,
            steward_positions=[(1.0, 0.5), (1.0, 0.5)],
        )
        assert gossip.phi > 0.0


# ===========================================================================
# process_inbound
# ===========================================================================

class TestProcessInbound:
    def test_creates_gossip_log_entry(self, db):
        payload = make_gossip(node_id="peer-A", checkpoint_index=1)
        entry = gossip_svc.process_inbound(payload, db)

        assert entry.id is not None
        assert entry.direction == "inbound"
        assert entry.peer_id == "peer-A"
        assert entry.checkpoint_index == 1
        assert entry.delivered is True
        assert entry.q_cross is not None
        assert isinstance(entry.created_at, datetime)

    def test_no_sign_flip_on_first_entry(self, db):
        payload = make_gossip(node_id="peer-new", checkpoint_index=1, za=0.5)
        entry = gossip_svc.process_inbound(payload, db)
        assert entry.sign_flip is False
        assert entry.anomaly_flagged is False

    def test_sign_flip_detected(self, db):
        # First entry: positive q_cross
        p1 = make_gossip(node_id="peer-flip", checkpoint_index=1, za=0.5, omega_a=2.0)
        gossip_svc.process_inbound(p1, db)

        # Second entry: opposite side of node_za so q_cross flips sign
        # za such that sin(za - node_za) is strongly negative
        p2 = make_gossip(node_id="peer-flip", checkpoint_index=2,
                         za=settings.node_za - math.pi / 2, omega_a=2.0)
        entry = gossip_svc.process_inbound(p2, db)

        assert entry.sign_flip is True
        assert entry.anomaly_flagged is True

    def test_below_threshold_no_flip(self, db):
        # q_cross below threshold — sign flip must not trigger
        p1 = make_gossip(node_id="peer-quiet", checkpoint_index=1,
                         za=settings.node_za + 0.01, omega_a=0.01)  # tiny magnitude
        gossip_svc.process_inbound(p1, db)
        p2 = make_gossip(node_id="peer-quiet", checkpoint_index=2,
                         za=settings.node_za - 0.01, omega_a=0.01)
        entry = gossip_svc.process_inbound(p2, db)
        assert entry.sign_flip is False


# ===========================================================================
# emit_gossip
# ===========================================================================

class TestEmitGossip:
    def _add_peer(self, db, peer_id, url):
        existing = db.query(Peer).filter_by(peer_id=peer_id).first()
        if existing:
            return existing
        peer = Peer(peer_id=peer_id, url=url)
        db.add(peer)
        db.commit()
        return peer

    def test_no_peers_no_log(self, db):
        # Clean db for this test
        db.query(GossipLog).filter_by(direction="outbound").delete()
        db.query(Peer).delete()
        db.commit()

        gossip_svc.emit_gossip(
            db=db,
            checkpoint_index=99,
            checkpoint_hash="0" * 64,
            ta_ref=0.0,
            steward_positions=[],
        )
        count = db.query(GossipLog).filter_by(checkpoint_index=99).count()
        assert count == 0

    def test_successful_delivery_updates_last_seen(self, db):
        peer = self._add_peer(db, "peer-emit-ok", "http://node-b.local:8000")
        assert peer.last_seen_checkpoint is None

        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.status_code = 200

        with patch("app.services.gossip.httpx.post", return_value=mock_resp):
            gossip_svc.emit_gossip(
                db=db,
                checkpoint_index=10,
                checkpoint_hash="a" * 64,
                ta_ref=1.0,
                steward_positions=[(1.0, 0.2)],
            )

        db.refresh(peer)
        assert peer.last_seen_checkpoint == 10
        assert peer.last_seen_at is not None

        log_entry = (
            db.query(GossipLog)
            .filter_by(peer_id="peer-emit-ok", checkpoint_index=10)
            .first()
        )
        assert log_entry is not None
        assert log_entry.delivered is True
        assert log_entry.direction == "outbound"

    def test_failed_delivery_logs_not_delivered(self, db):
        self._add_peer(db, "peer-emit-fail", "http://node-fail.local:8000")

        mock_resp = MagicMock()
        mock_resp.is_success = False
        mock_resp.status_code = 503

        with patch("app.services.gossip.httpx.post", return_value=mock_resp):
            gossip_svc.emit_gossip(
                db=db,
                checkpoint_index=11,
                checkpoint_hash="b" * 64,
                ta_ref=1.0,
                steward_positions=[],
            )

        log_entry = (
            db.query(GossipLog)
            .filter_by(peer_id="peer-emit-fail", checkpoint_index=11)
            .first()
        )
        assert log_entry is not None
        assert log_entry.delivered is False

    def test_network_error_logs_not_delivered(self, db):
        self._add_peer(db, "peer-emit-err", "http://node-err.local:8000")

        with patch("app.services.gossip.httpx.post", side_effect=Exception("timeout")):
            gossip_svc.emit_gossip(
                db=db,
                checkpoint_index=12,
                checkpoint_hash="c" * 64,
                ta_ref=1.0,
                steward_positions=[],
            )

        log_entry = (
            db.query(GossipLog)
            .filter_by(peer_id="peer-emit-err", checkpoint_index=12)
            .first()
        )
        assert log_entry is not None
        assert log_entry.delivered is False

    def test_last_seen_not_updated_on_failure(self, db):
        peer = self._add_peer(db, "peer-emit-noupdate", "http://node-noupdate.local:8000")
        peer.last_seen_checkpoint = None
        db.commit()

        with patch("app.services.gossip.httpx.post", side_effect=Exception("refused")):
            gossip_svc.emit_gossip(
                db=db,
                checkpoint_index=13,
                checkpoint_hash="d" * 64,
                ta_ref=1.0,
                steward_positions=[],
            )

        db.refresh(peer)
        assert peer.last_seen_checkpoint is None
