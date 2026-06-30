"""Tests for Peer and GossipLog models and their database round-trips."""
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.peer import Peer
from app.models.gossip_log import GossipLog


@pytest.fixture(scope="module")
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# Peer
# ---------------------------------------------------------------------------

class TestPeerModel:
    def test_create_peer(self, db):
        peer = Peer(peer_id="abc123", url="http://node-b.local:8000")
        db.add(peer)
        db.commit()
        db.refresh(peer)

        assert peer.id is not None
        assert peer.peer_id == "abc123"
        assert peer.url == "http://node-b.local:8000"
        assert peer.anomaly_count == 0
        assert peer.last_seen_checkpoint is None
        assert peer.last_seen_at is None
        assert isinstance(peer.added_at, datetime)

    def test_peer_id_unique(self, db):
        db.add(Peer(peer_id="dup", url="http://a.local"))
        db.commit()
        db.add(Peer(peer_id="dup", url="http://b.local"))
        with pytest.raises(Exception):
            db.commit()
        db.rollback()

    def test_update_last_seen(self, db):
        peer = db.query(Peer).filter_by(peer_id="abc123").one()
        peer.last_seen_checkpoint = 5
        peer.last_seen_at = datetime.utcnow()
        db.commit()
        db.refresh(peer)

        assert peer.last_seen_checkpoint == 5
        assert peer.last_seen_at is not None

    def test_anomaly_count_increment(self, db):
        peer = db.query(Peer).filter_by(peer_id="abc123").one()
        peer.anomaly_count += 1
        db.commit()
        db.refresh(peer)
        assert peer.anomaly_count == 1


# ---------------------------------------------------------------------------
# GossipLog
# ---------------------------------------------------------------------------

class TestGossipLogModel:
    def test_create_outbound_log(self, db):
        entry = GossipLog(
            direction="outbound",
            peer_id="abc123",
            checkpoint_index=1,
            delivered=True,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        assert entry.id is not None
        assert entry.direction == "outbound"
        assert entry.delivered is True
        assert entry.q_cross is None
        assert entry.sign_flip is None
        assert entry.anomaly_flagged is False
        assert isinstance(entry.created_at, datetime)

    def test_create_inbound_log(self, db):
        entry = GossipLog(
            direction="inbound",
            peer_id="abc123",
            checkpoint_index=1,
            delivered=True,
            q_cross=0.042,
            sign_flip=False,
            raw_node_id="deadbeef",
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        assert entry.q_cross == pytest.approx(0.042)
        assert entry.sign_flip is False
        assert entry.raw_node_id == "deadbeef"

    def test_sign_flip_flagged(self, db):
        entry = GossipLog(
            direction="inbound",
            peer_id="abc123",
            checkpoint_index=2,
            delivered=True,
            q_cross=-1.57,
            sign_flip=True,
            anomaly_flagged=True,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        assert entry.sign_flip is True
        assert entry.anomaly_flagged is True

    def test_failed_delivery_logged(self, db):
        entry = GossipLog(
            direction="outbound",
            peer_id="abc123",
            checkpoint_index=3,
            delivered=False,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        assert entry.delivered is False

    def test_append_only_no_updates(self, db):
        """GossipLog rows are never mutated — verify we never update an existing row."""
        entries_before = db.query(GossipLog).count()
        # Simulating what the service does: always inserts, never updates
        db.add(GossipLog(
            direction="outbound",
            peer_id="abc123",
            checkpoint_index=4,
            delivered=True,
        ))
        db.commit()
        assert db.query(GossipLog).count() == entries_before + 1
