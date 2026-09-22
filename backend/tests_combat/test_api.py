import time

import pytest
from arena.app import app
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("COMBAT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LAYA_ENABLED", "false")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with TestClient(app) as c:
        yield c


def test_catalog_profiles_preview_and_legacy_removed(client):
    data = client.get("/api/v2/catalog").json()
    assert len(data["fighters"]) == 4 and len(data["arenas"]) == 2
    assert client.get("/api/scenarios").status_code == 404
    assert client.post("/api/v2/preview", json={}).json()["fighters"][0]["character"] == "ember"
    assert "credential_env" not in client.get("/api/v2/profiles").text


def test_validates_humans_fighters_and_credentials(client):
    assert (
        client.post("/api/v2/matches", json={"players": [{"fighter_id": "missing"}, {}]}).status_code == 422
    )
    assert (
        client.post(
            "/api/v2/matches", json={"players": [{"controller": "human"}, {"controller": "human"}]}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v2/matches", json={"players": [{"controller": "model", "model_profile_id": "jev"}, {}]}
        ).status_code
        == 422
    )
    assert (
        client.post("/api/v2/matches", json={}, headers={"origin": "https://bad.example"}).status_code == 403
    )


def test_full_match_websocket_export_and_stop(client):
    r = client.post("/api/v2/matches", json={"max_seconds": 2})
    assert r.status_code == 201
    key = r.json()["id"]
    kinds = []
    with client.websocket_connect(f"/api/v2/matches/{key}/live") as ws:
        for _ in range(500):
            event = ws.receive_json()
            kinds.append(event["kind"])
            if event["kind"] == "finished":
                break
    assert "snapshot" in kinds and "decision" in kinds
    saved = client.get("/api/v2/matches/" + key).json()
    assert saved["status"] == "completed"
    assert all(p["counts"].get("applied", 0) > 0 for p in saved["players"])
    export = client.get(f"/api/v2/matches/{key}/export").text
    assert "manifest" in export and "apikey_" not in export


def test_human_input_ack_and_disconnect_pause(client):
    r = client.post(
        "/api/v2/matches",
        json={
            "mode": "training",
            "players": [{"controller": "human"}, {"model_profile_id": "dummy", "fighter_id": "flux"}],
        },
    )
    key = r.json()["id"]
    with client.websocket_connect(f"/api/v2/matches/{key}/live?role=controller") as ws:
        for _ in range(100):
            e = ws.receive_json()
            if e["kind"] == "snapshot" and e["state"]["phase"] == "active":
                break
        ws.send_json({"kind": "input", "player": 0, "seq": 1, "action": "forward"})
        for _ in range(100):
            e = ws.receive_json()
            if e["kind"] == "input_ack":
                break
        assert e["kind"] == "input_ack" and e["reason"] is None
    end = time.perf_counter() + 3
    while time.perf_counter() < end:
        if client.get("/api/v2/matches/" + key).json()["status"] == "paused":
            break
        time.sleep(0.02)
    assert client.get("/api/v2/matches/" + key).json()["status"] == "paused"
    assert (
        client.post(f"/api/v2/matches/{key}/control", json={"command": "stop"}).json()["status"] == "stopped"
    )
