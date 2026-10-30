"""
API integration tests for ScienceQuest Live FastAPI server.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_index_page():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "ScienceQuest Live" in resp.text
    assert "Two Worlds. Different Rules. One Curious Universe." in resp.text


def test_overlay_page():
    resp = client.get("/overlay")
    assert resp.status_code == 200
    assert "Audience Prediction Poll" in resp.text


def test_get_state():
    resp = client.get("/api/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_mission_id"] == "mission_1"
    assert "physics_result" in data
    assert "all_missions" in data
    assert len(data["all_missions"]) == 5


def test_update_parameter_endpoint():
    resp = client.post("/api/parameter", json={"param": "energy_ev", "value": 4.0})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["current_params"]["energy_ev"] == 4.0


def test_voting_flow_endpoints():
    # Start voting
    r_start = client.post("/api/voting/start", json={"duration_seconds": 30})
    assert r_start.status_code == 200
    assert r_start.json()["voting_open"] is True

    # Cast vote
    r_vote = client.post("/api/voting/vote", json={"username": "TestViewer", "option": "A"})
    assert r_vote.status_code == 200
    assert r_vote.json()["tallies"]["A"] >= 1

    # Resolve voting
    r_res = client.post("/api/voting/resolve")
    assert r_res.status_code == 200
    assert r_res.json()["correct_option"] == "A"


def test_ask_quark_endpoint():
    resp = client.post("/api/quark/ask", json={
        "question": "Why is classical transmission zero below the barrier?",
        "username": "Student",
        "level": "SCIENTIST"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["answer"]) > 10


def test_service_status():
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "simulation_mode" in data
    assert "twitch_connected" in data
    assert data["twitch_redirect_uri"] == "http://localhost:8000/auth/twitch/callback"


def test_twitch_oauth_login_unconfigured():
    from app.config import settings
    old_id = settings.twitch_client_id
    settings.twitch_client_id = ""
    resp = client.get("/auth/twitch/login", follow_redirects=False)
    assert resp.status_code == 400
    assert "TWITCH_CLIENT_ID" in resp.json()["error"]
    assert resp.json()["configured_redirect_uri"] == "http://localhost:8000/auth/twitch/callback"
    settings.twitch_client_id = old_id


def test_twitch_oauth_login_redirect():
    from app.config import settings
    old_id = settings.twitch_client_id
    settings.twitch_client_id = "mock_client_id_123"
    resp = client.get("/auth/twitch/login", follow_redirects=False)
    assert resp.status_code in (302, 307)
    loc = resp.headers["location"]
    assert "https://id.twitch.tv/oauth2/authorize" in loc
    assert "client_id=mock_client_id_123" in loc
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fauth%2Ftwitch%2Fcallback" in loc
    settings.twitch_client_id = old_id


def test_twitch_oauth_callback_missing_code():
    resp = client.get("/auth/twitch/callback")
    assert resp.status_code == 400
    assert "Authorization code missing" in resp.json()["detail"]


def test_twitch_oauth_callback_error():
    resp = client.get("/auth/twitch/callback?error=access_denied&error_description=User+denied", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "twitch_error=access_denied" in resp.headers["location"]

