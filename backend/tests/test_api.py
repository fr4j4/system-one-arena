import time

import pytest
from arena.app import app
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ARENA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LAYA_ENABLED", "false")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with TestClient(app) as c:
        yield c


def test_catalog_and_provider_configuration(client):
    assert client.get("/api/health").json()["ok"]
    assert len(client.get("/api/scenarios").json()) == 15
    providers = client.get("/api/providers").json()
    assert not next(p for p in providers if p["id"] == "jev")["configured"]
    assert "API_KEY" not in client.get("/api/providers").text
    for scenario in client.get("/api/scenarios").json():
        assert client.get("/api/preview/" + scenario["id"]).status_code == 200


def test_invalid_configuration_is_422(client):
    assert client.post("/api/runs", json={"scenario": "unknown"}).status_code == 422
    assert client.post("/api/runs", json={"budget_ms": -1}).status_code == 422
    assert client.post("/api/runs", json={"dataset": [{"bad": True}]}).status_code == 422


def test_cross_origin_requests_rejected(client):
    assert (
        client.post("/api/runs", json={}, headers={"origin": "https://untrusted.example"}).status_code == 403
    )


def test_websocket_run_and_export(client):
    response = client.post(
        "/api/runs",
        json={"scenario": "tickets", "provider": "reference", "budget_ms": 2000, "max_state_age_ms": 5000},
    )
    assert response.status_code == 201
    rid = response.json()["id"]
    kinds = []
    with client.websocket_connect(f"/api/runs/{rid}/live") as ws:
        initial = ws.receive_json()
        assert initial["kind"] == "initial"
        for _ in range(100):
            event = ws.receive_json()
            kinds.append(event["kind"])
            if event["kind"] == "finished":
                break
    assert "completed" in kinds and "applied" in kinds
    export = client.get(f"/api/runs/{rid}/export")
    assert export.status_code == 200 and '"manifest"' in export.text and '"accepted"' in export.text
    assert "apikey_" not in export.text


def test_graph_validation_and_dataset_persistence(client):
    graph = client.get("/api/graphs/support").json()
    assert client.post("/api/graphs/validate", json=graph).status_code == 200
    graph["nodes"][0]["next"] = graph["start"]
    assert client.post("/api/graphs/validate", json=graph).status_code == 422
    body = {
        "id": "data",
        "kind": "dataset",
        "name": "Test",
        "value": [{"state": {"text": "hi"}, "expected": {}}],
    }
    assert client.post("/api/presets", json=body).status_code == 200
    assert client.get("/api/presets").json()[0]["id"] == "data"


def test_paired_benchmark_same_input_and_no_response_cache(client):
    response = client.post(
        "/api/benchmarks",
        json={"scenario": "tickets", "providers": ["reference", "simulated"], "samples": 4, "warmup": 1},
    )
    assert response.status_code == 201
    key = response.json()["id"]
    end = time.perf_counter() + 10
    while time.perf_counter() < end:
        job = client.get("/api/benchmarks/" + key).json()
        if job["status"] != "running":
            break
        time.sleep(0.05)
    assert job["status"] == "completed", job
    left, right = job["results"]["reference"], job["results"]["simulated"]
    assert [r["state"] for r in left["rows"]] == [r["state"] for r in right["rows"]]
    assert left["latency"]["count"] == right["latency"]["count"] == 4
    assert right["latency"]["p50"] > 30


def test_live_metrics_are_sent_even_with_continuous_snapshots(client):
    response = client.post(
        "/api/runs",
        json={
            "scenario": "pong",
            "provider": "reference",
            "budget_ms": 2000,
            "max_state_age_ms": 5000,
            "max_seconds": 3,
        },
    )
    rid = response.json()["id"]
    with client.websocket_connect(f"/api/runs/{rid}/live") as ws:
        metrics = None
        for _ in range(700):
            event = ws.receive_json()
            if event["kind"] == "metrics":
                metrics = event
                break
            if event["kind"] == "finished":
                break
    assert metrics is not None, "Snapshots must not starve the periodic metrics heartbeat"
    assert metrics["status"] == "running"
