import asyncio
import time
from uuid import uuid4

from arena.adapters import ReferenceAdapter
from arena.protocol import RunConfig
from arena.runtime import Run
from arena.simulation import Simulation
from arena.storage import Store


async def wait_until(predicate, timeout=5):
    start = time.perf_counter()
    while not predicate():
        if time.perf_counter() - start > timeout:
            raise TimeoutError("condition not reached")
        await asyncio.sleep(0.01)


async def test_slow_inference_expires_but_does_not_block_simulation(tmp_path):
    store = Store(tmp_path)
    store.start()
    run = Run(
        RunConfig(scenario="pong", budget_ms=20, max_seconds=1),
        ReferenceAdapter("simulated", 140),
        store,
        asyncio.Semaphore(1),
    )
    await run.start()
    await run.task
    events = await store.events(run.id)
    assert any(e["kind"] == "expired" for e in events)
    assert not any(e["kind"] == "applied" for e in events)
    snapshots = [e for e in events if e["kind"] == "snapshot"]
    assert len(snapshots) >= 5
    assert snapshots[-1]["state"]["elapsed"] > 0.3
    await store.close()


async def test_step_mode_waits_and_replay_is_durable(tmp_path):
    store = Store(tmp_path)
    store.start()
    run = Run(
        RunConfig(scenario="tic-tac-toe", mode="step", budget_ms=2000, max_state_age_ms=5000),
        ReferenceAdapter(),
        store,
        asyncio.Semaphore(1),
    )
    await run.start()
    await wait_until(lambda: run.current is not None)
    assert not run.latencies
    before = run.current["state"]["board"][:]
    await run.control("step")
    await wait_until(lambda: bool(run.applied_ids))
    await run.stop()
    events = await store.events(run.id)
    assert any(e["kind"] == "applied" for e in events)
    assert any(e["kind"] == "snapshot" and e["state"]["board"] != before for e in events)
    assert (await store.run(run.id))["status"] == "stopped"
    await store.close()


async def test_business_flow_finishes_and_records_inputs(tmp_path):
    store = Store(tmp_path)
    store.start()
    run = Run(
        RunConfig(scenario="tickets", budget_ms=2000, max_state_age_ms=5000),
        ReferenceAdapter(),
        store,
        asyncio.Semaphore(1),
    )
    await run.start()
    await run.task
    assert run.status == "completed"
    assert len(run.business.results) == 4
    assert run.metrics()["quality"]["count"] == 12
    assert run.metrics()["provider_ms"]["count"] == 4
    await store.close()


def test_simulation_rejects_wrong_episode_expired_duplicate_and_illegal():
    config = RunConfig(scenario="pong", mode="step").model_dump()
    sim = Simulation(config, "episode")
    try:

        def collect_until(kind):
            start = time.perf_counter()
            while time.perf_counter() - start < 4:
                for e in sim.read():
                    if e["kind"] == kind:
                        return e
                time.sleep(0.01)
            raise TimeoutError(kind)

        snap = collect_until("snapshot")
        now = time.perf_counter_ns()
        command = {
            "kind": "action",
            "request_id": uuid4().hex,
            "episode_id": "wrong",
            "state_seq": snap["state_seq"],
            "captured_ns": now,
            "accepted_ns": now,
            "deadline_ns": now + 3_000_000_000,
            "valid_until_ns": now + 3_000_000_000,
            "action": "up",
        }
        sim.send(command)
        assert collect_until("rejected")["reason"] == "episode_mismatch"
        command.update(request_id=uuid4().hex, episode_id="episode", deadline_ns=now - 1)
        sim.send(command)
        assert collect_until("rejected")["reason"] == "expired"
        command.update(request_id=uuid4().hex, deadline_ns=now + 3_000_000_000)
        sim.send(command)
        collect_until("applied")
        sim.send(command)
        assert collect_until("rejected")["reason"] == "duplicate"
        command.update(request_id=uuid4().hex, action="unknown")
        sim.send(command)
        assert collect_until("rejected")["reason"] == "illegal_action"
    finally:
        sim.close()


async def test_provider_gate_does_not_overlap_physical_calls_after_expiry(tmp_path):
    class Counting(ReferenceAdapter):
        active = 0
        maximum = 0

        async def decide(self, req):
            self.active += 1
            self.maximum = max(self.maximum, self.active)
            try:
                return await super().decide(req)
            finally:
                self.active -= 1

    adapter = Counting("simulated", 100)
    store = Store(tmp_path)
    store.start()
    run = Run(
        RunConfig(scenario="tickets", budget_ms=10, max_seconds=1), adapter, store, asyncio.Semaphore(1)
    )
    await run.start()
    await run.task
    assert adapter.maximum == 1
    assert run.counts["expired"] > 0 and run.counts["applied"] == 0
    await store.close()


async def test_default_budget_applies_remote_latency_actions_in_games(tmp_path):
    for scenario in ("snake", "tetris"):
        store = Store(tmp_path / scenario)
        store.start()
        run = Run(
            RunConfig(scenario=scenario, max_seconds=2),
            ReferenceAdapter("simulated", 300),
            store,
            asyncio.Semaphore(1),
        )
        try:
            await run.start()
            await run.task
            assert run.counts["applied"] > 0, dict(run.counts)
        finally:
            await store.close()


async def test_stop_halts_physics_before_inflight_response_finishes(tmp_path):
    import pytest

    class Blocked(ReferenceAdapter):
        def __init__(self):
            super().__init__()
            self.entered = asyncio.Event()
            self.release = asyncio.Event()

        async def decide(self, request):
            self.entered.set()
            await self.release.wait()
            return await super().decide(request)

    adapter = Blocked()
    store = Store(tmp_path)
    store.start()
    run = Run(RunConfig(scenario="tetris"), adapter, store, asyncio.Semaphore(1))
    try:
        await run.start()
        await asyncio.wait_for(adapter.entered.wait(), 5)
        await run.control("stop")
        await wait_until(lambda: not run.sim.process.is_alive())
        assert not run.task.done()  # Physical call is still pending, physics has stopped.
        assert run.status == "stopped"
        with pytest.raises(ValueError, match="no está activa"):
            await run.control("resume")
        adapter.release.set()
        await run.task
        assert run.counts["applied"] == 0
        assert run.counts["accepted"] == 1
        assert run.counts["stopped"] == 1
    finally:
        adapter.release.set()
        await run.stop()
        await store.close()
