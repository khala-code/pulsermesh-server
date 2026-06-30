"""
Integration tests for app/routers/gossip.py.

Uses FastAPI TestClient with an in-memory SQLite database.
All gossip service calls are real (no mocks) except httpx.post
which is patched in emit path tests.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
from app.config import settings
from app.models.peer import Peer
from app.models.gossip_log import GossipLog


# ---------------------------------------------------------------------------
# Test DB override
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite:///:memory:"

@pytest.fixture(scope="module")
def test_db():
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    yield session
    session.close()


@pytest.fixture(scope="module")
def client(test_db):
    def override_get_db():
        try:
            yield test_db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


ADMIN_HEADERS = {"X-API-Key": settings.api_key_secret}

SAMPLE_GOSSIP = {
    "node_id": "remote-node-xyz",
    "checkpoint_index": 1,
    "checkpoint_hash": "ab" * 32,
    "za": 0.3,
    "omega_a": 1.0,
    "q_cross": 0.1,
    "phi": 0.8,
    "ta_ref": 1.0,
}


# ---------------------------------------------------------------------------
# POST /gossip
# ---------------------------------------------------------------------------

class TestReceiveGossip:
    def test_accepts_valid_payload(self, client):
        resp = client.post("/gossip", json=SAMPLE_GOSSIP)
        assert resp.status_code == 200
        body = resp.json()
        assert body["direction"] == "inbound"
        assert body["peer_id"] == "remote-node-xyz"
        assert body["delivered"] is True
        assert body["checkpoint_index"] == 1
        assert body["q_cross"] is not None

    def test_rejects_invalid_payload(self, client):
        resp = client.post("/gossip", json={"node_id": "x"})
        assert resp.status_code == 422

    def test_no_auth_required(self, client):
        # POST /gossip must succeed without any X-API-Key
        resp = client.post("/gossip", json=SAMPLE_GOSSIP)
        assert resp.status_code == 200

    def test_updates_last_seen_for_registered_peer(self, client, test_db):
        # Register the sender as a peer first
        test_db.add(Peer(peer_id="remote-node-xyz", url="http://remote.local:8000"))
        test_db.commit()

        resp = client.post("/gossip", json=SAMPLE_GOSSIP)
        assert resp.status_code == 200

        peer = test_db.query(Peer).filter_by(peer_id="remote-node-xyz").first()
        test_db.refresh(peer)
        assert peer.last_seen_checkpoint == 1
        assert peer.last_seen_at is not None

    def test_unregistered_sender_still_logged(self, client, test_db):
        payload = {**SAMPLE_GOSSIP, "node_id": "unknown-node-999"}
        resp = client.post("/gossip", json=payload)
        assert resp.status_code == 200
        entry = test_db.query(GossipLog).filter_by(peer_id="unknown-node-999").first()
        assert entry is not None


# ---------------------------------------------------------------------------
# GET /gossip/peers
# ---------------------------------------------------------------------------

class TestListPeers:
    def test_requires_admin_auth(self, client):
        resp = client.get("/gossip/peers")
        assert resp.status_code == 401

    def test_returns_peer_list(self, client):
        resp = client.get("/gossip/peers", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_peer_fields_present(self, client):
        resp = client.get("/gossip/peers", headers=ADMIN_HEADERS)
        peers = resp.json()
        if peers:
            p = peers[0]
            assert "peer_id" in p
            assert "url" in p
            assert "anomaly_count" in p
            assert "added_at" in p


# ---------------------------------------------------------------------------
# POST /gossip/peers
# ---------------------------------------------------------------------------

class TestAddPeer:
    def test_requires_admin_auth(self, client):
        resp = client.post("/gossip/peers", json={"peer_id": "x", "url": "http://x.local"})
        assert resp.status_code == 401

    def test_creates_peer(self, client):
        resp = client.post(
            "/gossip/peers",
            json={"peer_id": "new-peer-1", "url": "http://new-peer-1.local:8000"},
            headers=ADMIN_HEADERS,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["peer_id"] == "new-peer-1"
        assert body["url"] == "http://new-peer-1.local:8000"
        assert body["anomaly_count"] == 0
        assert body["last_seen_checkpoint"] is None

    def test_duplicate_peer_id_returns_409(self, client):
        client.post(
            "/gossip/peers",
            json={"peer_id": "dup-peer", "url": "http://dup.local"},
            headers=ADMIN_HEADERS,
        )
        resp = client.post(
            "/gossip/peers",
            json={"peer_id": "dup-peer", "url": "http://dup2.local"},
            headers=ADMIN_HEADERS,
        )
        assert resp.status_code == 409

    def test_blank_peer_id_rejected(self, client):
        resp = client.post(
            "/gossip/peers",
            json={"peer_id": "  ", "url": "http://x.local"},
            headers=ADMIN_HEADERS,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /gossip/peers/{peer_id}
# ---------------------------------------------------------------------------

class TestRemovePeer:
    def test_requires_admin_auth(self, client):
        resp = client.delete("/gossip/peers/some-peer")
        assert resp.status_code == 401

    def test_removes_peer(self, client):
        client.post(
            "/gossip/peers",
            json={"peer_id": "to-delete", "url": "http://del.local"},
            headers=ADMIN_HEADERS,
        )
        resp = client.delete("/gossip/peers/to-delete", headers=ADMIN_HEADERS)
        assert resp.status_code == 204

        # Confirm gone
        resp2 = client.delete("/gossip/peers/to-delete", headers=ADMIN_HEADERS)
        assert resp2.status_code == 404

    def test_delete_nonexistent_returns_404(self, client):
        resp = client.delete("/gossip/peers/does-not-exist", headers=ADMIN_HEADERS)
        assert resp.status_code == 404

    def test_gossip_log_retained_after_peer_removal(self, client, test_db):
        # Peer was registered and received gossip earlier in the test run
        log_count = test_db.query(GossipLog).filter_by(
            peer_id="remote-node-xyz"
        ).count()
        # Remove the peer
        client.delete("/gossip/peers/remote-node-xyz", headers=ADMIN_HEADERS)
        # Log rows must still be present (append-only)
        log_count_after = test_db.query(GossipLog).filter_by(
            peer_id="remote-node-xyz"
        ).count()
        assert log_count_after == log_count
