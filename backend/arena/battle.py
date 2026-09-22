"""Two independently paced model players controlling one authoritative fighting world."""

import asyncio
import time
from collections import Counter

from arena.metrics import percentiles
from arena.protocol import DecisionRequest
from arena.runtime import Run
from arena.simulation import Simulation


class BattleRun(Run):
    def __init__(self, config, adapters, store, gates):
        super().__init__(config, adapters[config.provider], store, gates[config.provider])
        self.config.controller = "model"
        self.config.options.update(best_of=config.best_of, round_seconds=config.round_seconds)
        self.adapters = {"p1": adapters[config.provider], "p2": adapters[config.player2_provider]}
        self.gates = {"p1": gates[config.provider], "p2": gates[config.player2_provider]}
        self.calls = {"p1": None, "p2": None}
        self.last_sent = {"p1": -1, "p2": -1}
        self.last_times = {"p1": 0.0, "p2": 0.0}
        self.slots = {
            player: {
                "provider": adapter.id,
                "counts": Counter(),
                "latencies": [],
                "last_request": None,
                "last_result": None,
                "failure_streak": 0,
                "error": None,
            }
            for player, adapter in self.adapters.items()
        }

    def summary(self):
        return {
            **super().summary(),
            "players": {
                key: {
                    "provider": slot["provider"],
                    "counts": dict(slot["counts"]),
                    "provider_ms": percentiles(slot["latencies"]),
                    "last_request": slot["last_request"],
                    "last_result": slot["last_result"],
                    "error": slot["error"],
                }
                for key, slot in self.slots.items()
            },
        }

    async def emit(self, kind, **payload):
        player = payload.get("player_id")
        if player in self.slots:
            payload.setdefault("provider", self.slots[player]["provider"])
            self.slots[player]["counts"][kind] += 1
        await super().emit(kind, **payload)

    async def _loop(self):
        try:
            await self.emit("preparing", message="Preparando los dos jugadores")
            prepared = {}
            for player, adapter in self.adapters.items():
                if self.status == "stopped":
                    return
                if adapter.id not in prepared:
                    async with self.gates[player]:
                        prepared[adapter.id] = await adapter.warmup()
            self.warmup_info = prepared
            if self.status == "stopped":
                return
            self.active_started = time.perf_counter()
            self.sim = Simulation(self.config.model_dump(), self.episode)
            self.status = "running"
            await self.emit("ready", warmup=prepared)
            while self.status in ("running", "paused"):
                for item in self.sim.read():
                    kind = item.pop("kind")
                    if kind == "snapshot":
                        self.current = item
                    elif kind == "applied":
                        self.e2e.append(item["end_to_end_ms"])
                        self.ages.append(item["age_ms"])
                        self.applied_ids.add(item["request_id"])
                    await self.emit(kind, **item)
                if self.status == "stopped":
                    break
                if not self.sim.process.is_alive():
                    raise RuntimeError("El proceso de combate terminó inesperadamente")
                if self.current and self.current["state"]["done"]:
                    self.status = "completed"
                    break
                if time.perf_counter() - self.active_started >= self.config.max_seconds:
                    self.status = "completed"
                    await self.emit("time_limit")
                    break
                for player in self.calls:
                    task = self.calls[player]
                    if task and task.done():
                        await task
                        self.calls[player] = None
                    if (
                        self.status == "running"
                        and not self.paused
                        and self.current
                        and self.current["state"]["phase"] == "active"
                        and not self.calls[player]
                        and len(self.current["player_views"][player]["allowed_actions"]) > 1
                        and self.current["state_seq"] != self.last_sent[player]
                        and time.perf_counter() - self.last_times[player] >= 1 / self.config.decision_hz
                    ):
                        self.last_sent[player] = self.current["state_seq"]
                        self.last_times[player] = time.perf_counter()
                        self.calls[player] = asyncio.create_task(self._decide_player(player, self.current))
                await asyncio.sleep(0.005)
        except Exception as exc:
            self.status, self.error = "failed", str(exc)
            await self.emit("failed", error=self.error)
        finally:
            self.ended = time.perf_counter()
            if self.sim:
                self.sim.stopping.set()
            await asyncio.gather(*(task for task in self.calls.values() if task), return_exceptions=True)
            if self.sim:
                await asyncio.to_thread(self.sim.close)
            await self.emit(
                "finished", status=self.status, metrics=self.metrics(), players=self.summary()["players"]
            )
            await self.store.save_run(self.summary())

    async def _decide_player(self, player, snapshot):
        adapter, gate, slot = self.adapters[player], self.gates[player], self.slots[player]
        accepted = time.perf_counter_ns()
        view = snapshot["player_views"][player]
        request = DecisionRequest(
            run_id=self.id,
            episode_id=self.episode,
            state_seq=snapshot["state_seq"],
            schema_id="fighting/2",
            state=view["state"],
            questions=view["questions"],
            allowed_actions=view["allowed_actions"],
            budget_ms=self.config.budget_ms,
            max_state_age_ms=self.config.max_state_age_ms,
        )
        rid = request.request_id
        deadline = accepted + self.config.budget_ms * 1_000_000

        async def emit(kind, **data):
            await self.emit(
                kind, player_id=player, provider=adapter.id, request_id=rid, round=snapshot["round"], **data
            )

        slot["last_request"] = self.last_request = request.model_dump()
        await emit("accepted", request=slot["last_request"])
        await emit("queued")
        acquired = False
        try:
            try:
                await asyncio.wait_for(gate.acquire(), max(0.001, (deadline - time.perf_counter_ns()) / 1e9))
                acquired = True
            except TimeoutError:
                await emit("expired", stage="queue")
                return
            started = time.perf_counter_ns()
            if self.status != "running" or self.paused or started >= deadline:
                await emit("rejected", reason="run_not_active_or_deadline")
                return
            queue_ms = (started - accepted) / 1e6
            self.queues.append(queue_ms)
            await emit("started", queue_ms=queue_ms)
            future = asyncio.create_task(adapter.decide(request))
            expired = False
            try:
                result = await asyncio.wait_for(
                    asyncio.shield(future), max(0.001, (deadline - time.perf_counter_ns()) / 1e9)
                )
            except TimeoutError:
                expired = True
                await emit("expired", stage="provider")
                result = await future
            ended = time.perf_counter_ns()
            latency = (ended - started) / 1e6
            self.latencies.append(latency)
            slot["latencies"].append(latency)
            if result.timings.get("inference_ms") is not None:
                self.inferences.append(result.timings["inference_ms"])
            result.timings.update(provider_ms=latency, queue_ms=queue_ms)
            slot["last_result"] = self.last_result = result.model_dump()
            slot["failure_streak"] = 0
            await emit("completed", result=slot["last_result"], late=expired)
            if self.status != "running" or self.paused:
                await emit("rejected", reason="run_not_active")
                return
            if (
                expired
                or ended > deadline
                or ended - snapshot["captured_ns"] > self.config.max_state_age_ms * 1e6
            ):
                if not expired:
                    await emit("expired", stage="state_age")
                return
            self.sim.send(
                {
                    "kind": "action",
                    "player_id": player,
                    "round": snapshot["round"],
                    "action": result.answers["action"].value,
                    "request_id": rid,
                    "episode_id": self.episode,
                    "state_seq": snapshot["state_seq"],
                    "captured_ns": snapshot["captured_ns"],
                    "accepted_ns": accepted,
                    "deadline_ns": deadline,
                    "valid_until_ns": snapshot["captured_ns"] + self.config.max_state_age_ms * 1_000_000,
                }
            )
        except Exception as exc:
            slot["failure_streak"] += 1
            slot["error"] = str(exc)
            await emit("failed", error=str(exc))
            if slot["failure_streak"] >= 3:
                self.status, self.error = "failed", f"{player.upper()}: {exc}"
                self.sim.stopping.set()
        finally:
            if acquired:
                gate.release()
