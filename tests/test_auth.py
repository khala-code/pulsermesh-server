import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


def test_missing_api_key_returns_401(tmp_path):
    """Any protected endpoint without a key returns 401."""
    from app.main import app
    client = TestClient(app)
    response = client.get("/checkpoint/current")
    assert response.status_code == 401


def test_wrong_api_key_returns_401():
    from app.main import app
    client = TestClient(app)
    response = client.get("/checkpoint/current", headers={"X-API-Key": "wrongkey"})
    assert response.status_code == 401


def test_correct_node_key_passes_auth():
    """Node key from settings passes require_api_key."""
    from app.main import app
    from app.config import settings
    client = TestClient(app)
    response = client.get("/checkpoint/current", headers={"X-API-Key": settings.api_key_secret})
    # 200 or any non-401 means auth passed
    assert response.status_code != 401


def test_steward_key_rejected_on_node_only_endpoint():
    """A pm_ key must not pass node-only endpoints."""
    from app.main import app
    client = TestClient(app)
    response = client.get("/checkpoint/current", headers={"X-API-Key": "pm_fakekeyfakekeyfakekeyfakekeyfakekeyfakekeyfakekeyfakekeyfakekey12"})
    assert response.status_code == 401
