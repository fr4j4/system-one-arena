import asyncio
import json
import queue
import sqlite3
import threading
import time

import httpx
import pytest
from arena.combat import session
from arena.combat.profiles import Profile, Registry, Remote
from arena.combat.protocol import MatchConfig, SeriesConfig
from arena.combat.series import Series
from arena.combat.worker import CombatProcess, worker
from arena.protocol import DecisionRequest, Question
from arena.storage import Store
from test_runtime import Recorder, launch, runtime  # noqa: F401


async def test_equal_windows_pacing_does_not_hold_shared_gate(runtime):  # noqa: F811
    runtime[0].gates["reference"] = asyncio.Semaphore(1)
    m = await launch(runtime, Recorder(0.05), pace="equal_windows", budget_ms=300, max_seconds=4)
    await m.task
    players = m.view()["players"]
    assert all(p["counts"].get("completed", 0) >= 2 for p in players)
    assert sum(p["counts"].get("expired", 0) for p in players) == 0


async def test_store_failure_still_closes_combat_process(tmp_path, monkeypatch):
    closed = []

    class Tracked(CombatProcess):
        def close(self):
            closed.append(True)
            super().close()

    monkeypatch.setattr(session, "CombatProcess", Tracked)
    store = Store(tmp_path)
    write = store._write

    def failing(batch):
        if any(item[0] == "event" for item in batch):
            raise sqlite3.OperationalError("disk full")
        write(batch)

    store._write = failing
    store.start()
    registry = Registry()
    m = session.Match(MatchConfig(max_seconds=3), registry, store)
    await m.start()
    with pytest.raises(sqlite3.OperationalError):
        await asyncio.wait_for(m.task, 10)
    assert closed == [True]
    await registry.close()
    await asyncio.gather(store.task, return_exceptions=True)


def test_worker_survives_full_outgoing_queue_without_dropping_events():
    incoming, outgoing, stopping = queue.Queue(), queue.Queue(1), threading.Event()
    thread = threading.Thread(target=worker, args=(MatchConfig().model_dump(), incoming, outgoing, stopping))
    thread.start()
    try:
        incoming.put(dict(kind="pause"))
        time.sleep(0.6)
        assert thread.is_alive()
        kinds = []
        end = time.monotonic() + 2
        while "controlled" not in kinds and time.monotonic() < end:
            kinds.append(outgoing.get(timeout=1)["kind"])
        assert "controlled" in kinds
    finally:
        stopping.set()
        thread.join(2)
    assert not thread.is_alive()


async def test_series_stop_keeps_terminal_status(runtime):  # noqa: F811
    registry, store, _ = runtime
    s = Series(SeriesConfig(pairs=1), registry, store)
    s.status = "completed"
    await s.stop()
    assert s.status == "completed"


def request():
    return DecisionRequest(
        run_id="r",
        episode_id="r:0",
        state_seq=0,
        schema_id="combat/1",
        state={"x": 1},
        questions={
            "action": Question(type="choice", instructions="Pick", criteria={"forward": "go", "block": "b"})
        },
        allowed_actions=["forward", "block"],
    )


def remote(monkeypatch, provider, handler):
    monkeypatch.setenv("ARENA_TEST_KEY", "k")
    adapter = Remote(
        Profile(
            id="t",
            name="T",
            provider=provider,
            model="m",
            endpoint="https://provider.test/v1",
            credential_env="ARENA_TEST_KEY",
        )
    )
    adapter.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return adapter


async def test_remote_jev_success_and_http_error(monkeypatch):
    seen = []

    def handler(req):
        seen.append(req)
        if len(seen) > 1:
            return httpx.Response(429, json={"error": "quota"})
        return httpx.Response(
            200, json={"model": "jev-x", "answers": {"action": {"type": "choice", "choice": "block"}}}
        )

    adapter = remote(monkeypatch, "jev", handler)
    result = await adapter.decide(request())
    assert result.answers["action"].value == "block" and result.model == "jev-x"
    assert str(seen[0].url) == "https://provider.test/v1"
    assert seen[0].headers["authorization"] == "Bearer k"
    assert json.loads(seen[0].content)["questions"]["action"]["type"] == "choice"
    with pytest.raises(ValueError, match="HTTP 429"):
        await adapter.decide(request())
    await adapter.close()


async def test_remote_generic_chat_completions(monkeypatch):
    replies = [
        dict(
            model="gpt-x",
            usage={"total_tokens": 3},
            choices=[
                dict(
                    message=dict(
                        content=json.dumps(
                            {
                                "answers": {
                                    "action": {
                                        "type": "choice",
                                        "choice": "forward",
                                        "confidence": 0.99,
                                        "probabilities": {"forward": 1},
                                    }
                                }
                            }
                        )
                    )
                )
            ],
        ),
        dict(choices=[dict(message=dict(content="not json"))]),
        dict(choices=[dict(message=dict(content='{"answers": {}}'))]),
    ]
    urls = []

    def handler(req):
        urls.append(str(req.url))
        if len(urls) > len(replies):
            return httpx.Response(500)
        return httpx.Response(200, json=replies[len(urls) - 1])

    adapter = remote(monkeypatch, "generic", handler)
    result = await adapter.decide(request())
    assert urls[0] == "https://provider.test/v1/chat/completions"
    assert result.model == "gpt-x" and result.usage == {"total_tokens": 3}
    answer = result.answers["action"]
    assert answer.value == "forward" and answer.confidence is None and answer.probabilities is None
    with pytest.raises(ValueError):
        await adapter.decide(request())
    with pytest.raises(ValueError, match="Missing answer"):
        await adapter.decide(request())
    with pytest.raises(ValueError, match="HTTP 500"):
        await adapter.decide(request())
    await adapter.close()
