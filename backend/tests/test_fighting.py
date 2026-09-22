import asyncio
import time
from uuid import uuid4

import pytest
from arena.adapters import ReferenceAdapter
from arena.battle import BattleRun
from arena.protocol import RunConfig
from arena.scenarios.fighting import FightingWorld
from arena.simulation import Simulation
from arena.storage import Store


def advance(world, seconds):
    for _ in range(round(seconds * 100)):
        world.tick(0.01)


def active(**options):
    world = FightingWorld(options)
    advance(world, 0.9)
    assert world.phase == "active"
    return world


def test_planar_motion_jump_and_perspectives():
    world = active(round_seconds=120)
    world.apply("approach", 0)
    world.apply("approach", 1)
    advance(world, 1)
    assert -4 < world.fighters[0]["x"] < world.fighters[1]["x"] < 4
    world.apply("jump", 0)
    advance(world, 0.2)
    assert world.fighters[0]["y"] > 0
    advance(world, 1)
    assert world.fighters[0]["y"] == 0
    for i in range(2):
        world.apply("retreat", i)
    advance(world, 5)
    assert all(abs(p["x"]) <= 8 and p["z"] == 0 for p in world.fighters)
    assert world.perspective(0)["self"] == world.perspective(1)["opponent"]
    assert "player 2" in world.questions(1)["action"].instructions


@pytest.mark.parametrize("guard,damage", [(False, 16), (True, 4)])
def test_melee_windup_guard_and_energy(guard, damage):
    world = active()
    world.fighters[0]["x"], world.fighters[1]["x"] = -0.7, 0.7
    if guard:
        world.apply("block", 1)
    assert world.apply("heavy", 0)
    assert world.fighters[0]["energy"] == 86
    assert not world.apply("heavy", 0)
    advance(world, 0.1)
    assert world.fighters[1]["health"] == 100
    advance(world, 0.2)
    assert world.fighters[1]["health"] == 100 - damage


def test_projectile_travel_jump_evasion_and_special_cost():
    world = active()
    assert world.apply("special", 0)
    assert world.fighters[0]["energy"] == 40
    advance(world, 0.5)
    assert len(world.projectiles) == 1
    assert world.fighters[1]["health"] == 100
    advance(world, 1)
    assert world.fighters[1]["health"] == 70
    assert "special" not in world.legal_actions(0)
    evade = active()
    evade.apply("projectile", 0)
    advance(evade, 0.85)
    evade.apply("jump", 1)
    advance(evade, 0.6)
    assert evade.fighters[1]["health"] == 100


def test_round_reset_best_of_and_bounded_ties():
    world = active(best_of=3)
    for round_number in (1, 2):
        world.fighters[1]["health"] = 0
        world.tick(0.01)
        assert world.history[-1]["winner"] == "p1"
        if round_number == 1:
            assert not world.done
            advance(world, 3)
            assert world.round == 2
            assert all(p["health"] == 100 for p in world.fighters)
    assert world.done and world.winner == "p1" and world.wins == [2, 0]
    draw = active(best_of=1, round_seconds=5)
    advance(draw, 30)
    assert draw.done and draw.outcome == "draw" and len(draw.history) == 3


class Recording(ReferenceAdapter):
    def __init__(self, name, delay=0):
        super().__init__(name, delay)
        self.requests = []
        self.active = self.maximum = 0

    async def decide(self, request):
        self.requests.append(request)
        self.active += 1
        self.maximum = max(self.maximum, self.active)
        try:
            return await super().decide(request)
        finally:
            self.active -= 1


async def wait_for(predicate, seconds=8):
    deadline = time.perf_counter() + seconds
    while not predicate():
        if time.perf_counter() > deadline:
            raise TimeoutError("Battle condition not reached")
        await asyncio.sleep(0.02)


async def test_two_independent_players_pause_resume_and_stop(tmp_path):
    fast, slow = Recording("reference"), Recording("simulated", 220)
    adapters = {p.id: p for p in (fast, slow)}
    store = Store(tmp_path)
    store.start()
    run = BattleRun(
        RunConfig(scenario="fighting", provider="reference", player2_provider="simulated", decision_hz=20),
        adapters,
        store,
        {key: asyncio.Semaphore(1) for key in adapters},
    )
    try:
        await run.start()
        await wait_for(lambda: run.slots["p2"]["counts"]["applied"] >= 3)
        assert len(fast.requests) > len(slow.requests)
        assert {r.state["player_id"] for r in fast.requests} == {"p1"}
        assert {r.state["player_id"] for r in slow.requests} == {"p2"}
        await run.control("pause")
        await asyncio.sleep(0.35)
        counts = [len(a.requests) for a in (fast, slow)]
        state = run.current["state"]
        await asyncio.sleep(0.3)
        assert counts == [len(a.requests) for a in (fast, slow)]
        assert state == run.current["state"]
        await run.control("resume")
        await wait_for(lambda: len(fast.requests) > counts[0])
        await run.stop()
        counts = [len(a.requests) for a in (fast, slow)]
        await asyncio.sleep(0.2)
        assert counts == [len(a.requests) for a in (fast, slow)]
        assert run.status == "stopped" and run.sim.process._closed
        events = await store.events(run.id)
        assert {e["player_id"] for e in events if e["kind"] == "applied"} == {"p1", "p2"}
        assert all(a.maximum == 1 for a in (fast, slow))
    finally:
        await run.stop()
        await store.close()


async def test_same_provider_shares_gate_and_both_slots_progress(tmp_path):
    adapter = Recording("reference", 70)
    store = Store(tmp_path)
    store.start()
    run = BattleRun(
        RunConfig(scenario="fighting", provider="reference", max_seconds=3),
        {"reference": adapter},
        store,
        {"reference": asyncio.Semaphore(1)},
    )
    try:
        await run.start()
        await run.task
        assert run.status == "completed", run.error
        assert adapter.maximum == 1
        assert all(run.slots[p]["counts"]["applied"] > 0 for p in ("p1", "p2"))
    finally:
        await run.stop()
        await store.close()


def test_simulation_rejects_old_round_and_invalid_player():
    sim = Simulation(RunConfig(scenario="fighting").model_dump(), "battle")

    def receive(kind):
        deadline = time.perf_counter() + 5
        while time.perf_counter() < deadline:
            for event in sim.read():
                if event["kind"] == kind:
                    return event
            time.sleep(0.01)
        raise TimeoutError(kind)

    try:
        snap = receive("snapshot")
        now = time.perf_counter_ns()
        command = dict(
            kind="action",
            request_id=uuid4().hex,
            episode_id="battle",
            state_seq=snap["state_seq"],
            captured_ns=now,
            accepted_ns=now,
            deadline_ns=now + 5_000_000_000,
            valid_until_ns=now + 5_000_000_000,
            action="neutral",
            player_id="p1",
            round=0,
        )
        sim.send(command)
        assert receive("rejected")["reason"] == "round_mismatch"
        command.update(request_id=uuid4().hex, round=1, player_id="p3")
        sim.send(command)
        assert receive("rejected")["reason"] == "invalid_player"
    finally:
        sim.close()


async def test_stop_stops_world_while_both_physical_calls_are_pending(tmp_path):
    class Blocked(Recording):
        def __init__(self):
            super().__init__("reference")
            self.entered = 0
            self.release = asyncio.Event()

        async def decide(self, request):
            self.entered += 1
            await self.release.wait()
            return await super().decide(request)

    adapter = Blocked()
    store = Store(tmp_path)
    store.start()
    run = BattleRun(
        RunConfig(scenario="fighting", provider="reference"),
        {"reference": adapter},
        store,
        {"reference": asyncio.Semaphore(2)},
    )
    try:
        await run.start()
        await wait_for(lambda: adapter.entered == 2)
        await run.control("stop")
        await wait_for(lambda: not run.sim.process.is_alive())
        assert not run.task.done()
        adapter.release.set()
        await run.task
        assert run.status == "stopped" and adapter.entered == 2
        assert run.counts["applied"] == 0
        assert run.counts["rejected"] == 2
    finally:
        adapter.release.set()
        await run.stop()
        await store.close()


def test_fighting_corpus_uses_player_perspective_and_active_opponent():
    from arena.benchmark import BenchmarkConfig, corpus

    items = corpus(BenchmarkConfig(scenario="fighting", samples=50))
    assert all(row["state"]["player_id"] == "p1" for row in items)
    assert all(row["state"]["phase"] == "active" for row in items)
    assert any(row["state"]["self"]["health"] < 100 for row in items)
    assert any(row["state"]["opponent"]["energy"] < 100 for row in items)


async def test_battle_finishes_rounds_and_stops_querying(tmp_path):
    adapters = {name: Recording(name) for name in ("reference", "random")}
    store = Store(tmp_path)
    store.start()
    run = BattleRun(
        RunConfig(
            scenario="fighting",
            provider="reference",
            player2_provider="random",
            best_of=1,
            round_seconds=5,
            speed=3,
            max_seconds=12,
        ),
        adapters,
        store,
        {k: asyncio.Semaphore(1) for k in adapters},
    )
    try:
        await run.start()
        await asyncio.wait_for(run.task, 15)
        assert run.status == "completed"
        assert run.current["state"]["phase"] == "finished"
        assert run.current["state"]["rounds"]
        counts = {key: len(a.requests) for key, a in adapters.items()}
        await asyncio.sleep(0.15)
        assert counts == {key: len(a.requests) for key, a in adapters.items()}
        saved = await store.run(run.id)
        assert saved["players"]["p1"]["counts"]["applied"] > 0
        assert saved["players"]["p2"]["counts"]["applied"] > 0
    finally:
        await run.stop()
        await store.close()
