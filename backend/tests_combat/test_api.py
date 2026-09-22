import time

import pytest
from arena.app import app
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("COMBAT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LAYA_ENABLED", "false")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setenv("ARENA_ALLOWED_HOSTS", "testserver")
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
    with client.websocket_connect(f"/api/v2/matches/{key}/live?role=controller") as ws:
        client.post(f"/api/v2/matches/{key}/control", json={"command": "resume"})
        for _ in range(100):
            e = ws.receive_json()
            if e["kind"] == "snapshot" and e["state"]["phase"] == "active":
                break
        ws.send_json({"kind": "input", "player": 0, "seq": 1, "action": "forward"})
        for _ in range(100):
            e = ws.receive_json()
            if e["kind"] == "input_ack":
                break
        assert e["reason"] is None
    assert (
        client.post(f"/api/v2/matches/{key}/control", json={"command": "stop"}).json()["status"] == "stopped"
    )


def test_foreign_host_rejected_on_http_and_websocket(client):
    assert client.get("/api/v2/health").status_code == 200
    assert client.get("/api/v2/health", headers={"host": "localhost:8000"}).status_code == 200
    assert client.get("/api/v2/health", headers={"host": "[::1]:8000"}).status_code == 200
    lan = {"host": "192.168.1.5:5173", "origin": "http://192.168.1.5:5173"}
    assert client.get("/api/v2/health", headers=lan).status_code == 200
    spoof = {"host": "192.168.1.5:5173", "origin": "http://rebind.attacker.example"}
    assert client.get("/api/v2/health", headers=spoof).status_code == 403
    evil = {"host": "rebind.attacker.example:8000", "origin": "http://rebind.attacker.example:8000"}
    assert client.get("/api/v2/health", headers=evil).status_code == 403
    key = client.post("/api/v2/matches", json={"max_seconds": 5}).json()["id"]
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/v2/matches/{key}/live", headers=evil) as ws:
            ws.receive_json()
    client.post(f"/api/v2/matches/{key}/control", json={"command": "stop"})


def test_malformed_websocket_messages_are_ignored(client):
    key = client.post(
        "/api/v2/matches",
        json={
            "mode": "training",
            "players": [{"controller": "human"}, {"model_profile_id": "dummy", "fighter_id": "flux"}],
        },
    ).json()["id"]
    with client.websocket_connect(f"/api/v2/matches/{key}/live?role=controller") as ws:
        for _ in range(100):
            e = ws.receive_json()
            if e["kind"] == "snapshot" and e["state"]["phase"] == "active":
                break
        ws.send_text("not json")
        ws.send_text("[]")
        ws.send_bytes(b"\x00")
        ws.send_json({"kind": "input", "player": 0, "seq": 1, "action": "forward"})
        for _ in range(200):
            e = ws.receive_json()
            if e["kind"] == "input_ack":
                break
        assert e["kind"] == "input_ack"
        assert client.get("/api/v2/matches/" + key).json()["status"] == "running"
    client.post(f"/api/v2/matches/{key}/control", json={"command": "stop"})
