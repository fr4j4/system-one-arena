import asyncio
import copy
import time

import pytest
from arena.combat.engine import World
from arena.combat.observation import observe
from arena.combat.profiles import Registry
from arena.combat.protocol import MatchConfig, SeriesConfig
from arena.combat.series import Series
from arena.combat.session import Match
from arena.combat.worker import CombatProcess
from arena.protocol import normalize
from arena.storage import Store


class Recorder:
    def __init__(self, delay=0, fail=False):
        self.delay, self.fail = delay, fail
        self.started = 0
        self.pending = 0
        self.maximum = 0

    async def warmup(self):
        return {"ready": True}

    async def decide(self, req):
        self.started += 1
        self.pending += 1
        self.maximum = max(self.maximum, self.pending)
        try:
            await asyncio.sleep(self.delay)
            if self.fail:
                raise ValueError("test provider unavailable")
            action = "forward" if "forward" in req.allowed_actions else req.allowed_actions[0]
            return normalize({"answers": {"action": {"type": "choice", "choice": action}}}, req, "test")
        finally:
            self.pending -= 1

    async def close(self):
        pass


async def until(predicate, timeout=6):
    start = time.monotonic()
    while not predicate():
        if time.monotonic() - start > timeout:
            raise AssertionError("timed out waiting for runtime state")
        await asyncio.sleep(0.015)


@pytest.fixture
async def runtime(tmp_path):
    store = Store(tmp_path)
    store.start()
    registry = Registry()
    matches = []
    yield registry, store, matches
    for match in matches:
        await match.stop()
    await registry.close()
    await store.close()


async def launch(runtime, adapter, **kwargs):
    registry, store, matches = runtime
    await registry.adapters["reference"].close()
    registry.adapters["reference"] = adapter
    config = MatchConfig(**kwargs)
    match = Match(config, registry, store)
    matches.append(match)
    await match.start()
    return match


async def test_pause_and_stop_stop_calls_and_physics(runtime):
    adapter = Recorder(0.15)
    m = await launch(runtime, adapter)
    await until(lambda: adapter.started >= 2)
    await m.control("pause")
    await asyncio.sleep(0.3)
    count, tick = adapter.started, m.snapshot["tick"]
    await asyncio.sleep(0.4)
    assert adapter.started == count
    assert m.snapshot["tick"] == tick
    await m.control("resume")
    await until(lambda: adapter.started > count)
    await m.control("stop")
    count = adapter.started
    await m.task
    assert adapter.started == count and m.status == "stopped"


async def test_late_calls_keep_one_physical_call_per_slot(runtime):
    adapter = Recorder(1.2)
    m = await launch(runtime, adapter, budget_ms=100, max_seconds=3)
    await m.task
    assert adapter.maximum <= 2
    assert all(p["counts"]["expired"] >= 1 for p in m.view()["players"])
    assert all(p["counts"].get("applied", 0) == 0 for p in m.view()["players"])


async def test_shared_gate_limits_physical_provider_work(runtime):
    adapter = Recorder(0.25)
    m = await launch(runtime, adapter, max_seconds=3)
    runtime[0].gates["reference"] = asyncio.Semaphore(1)
    await m.task
    assert adapter.maximum == 1 and adapter.started >= 4


async def test_three_provider_errors_pause_without_fallback(runtime):
    m = await launch(runtime, Recorder(fail=True))
    await until(lambda: m.status == "paused")
    assert "unavailable" in m.error
    assert not any(p["counts"].get("applied") for p in m.view()["players"])


async def test_reset_epoch_monotonic_and_old_action_rejected():
    proc = CombatProcess(MatchConfig(mode="training").model_dump())
    packets = []
    try:

        async def read():
            await asyncio.sleep(0.08)
            packets.extend(proc.read())

        for _ in range(15):
            await read()
            if packets:
                break
        old = next(p["state"]["epoch"] for p in packets if p["kind"] == "snapshot")
        for _ in range(3):
            proc.send({"kind": "reset"})
            await read()
        epoch = [p["state"]["epoch"] for p in packets if p["kind"] == "snapshot"][-1]
        assert epoch >= old + 3
        proc.send({"kind": "action", "player": 0, "action": "forward", "epoch": old, "source": "model"})
        await read()
        assert any(p.get("reason") == "context_changed" for p in packets)
    finally:
        await asyncio.to_thread(proc.close)


async def test_clash_observation_and_ack_do_not_reveal_pending_choice():
    world = World(MatchConfig().model_dump())
    world.begin_clash()
    before = copy.deepcopy(observe(world, 1))
    world.apply(0, "surge")
    assert observe(world, 1) == before
    assert "choices" not in world.snapshot()["clash"]


async def test_paired_series_completes_and_swaps_slots(runtime):
    registry, store, _ = runtime
    s = Series(SeriesConfig(match=MatchConfig(max_seconds=1), pairs=1), registry, store)
    await s.run()
    assert s.status == "completed" and len(s.results) == 2
    assert s.results[0]["config"]["players"] == list(reversed(s.results[1]["config"]["players"]))


async def test_failed_series_does_not_hang_on_paused_match(runtime):
    registry, store, _ = runtime
    registry.adapters["reference"] = Recorder(fail=True)
    s = Series(SeriesConfig(pairs=1), registry, store)
    await asyncio.wait_for(s.run(), 8)
    assert s.status == "failed" and "unavailable" in s.error
