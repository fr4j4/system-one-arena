"""Live coordinator. Stale results are observable, never silently applied."""

from __future__ import annotations

import asyncio
import time
from collections import Counter, deque
from datetime import UTC, datetime
from uuid import uuid4

from arena.metrics import evaluate, hardware, percentiles
from arena.protocol import DecisionRequest
from arena.scenarios.business import Business, fixtures, validate_dataset
from arena.scenarios.datasets import sample
from arena.scenarios.games import CATALOG
from arena.simulation import Simulation

GAMES = {x[0] for x in CATALOG}


class Run:
    def __init__(self, config, adapter, store, gate):
        config = config.model_copy(deep=True)
        if config.execution != "turns":
            config.mode = "realtime"
        if config.execution == "batch":
            config.controller = "model"
        if config.execution == "realtime" and config.options.get("experience") == "evaluate":
            config.speed = 1
        self.id, self.episode = uuid4().hex, uuid4().hex
        self.config, self.adapter, self.store, self.gate = config, adapter, store, gate
        self.created_at = datetime.now(UTC).isoformat()
        self.status, self.error, self.paused = "preparing", None, False
        self.seq, self.current, self.sim, self.business = 0, None, None, None
        self.subscribers = set()
        self.recent = deque(maxlen=300)
        self.counts = Counter()
        self.latencies, self.e2e, self.ages = [], [], []
        self.inferences, self.queues, self.overheads, self.paints = [], [], [], []
        self.last_result, self.last_request = None, None
        self.started = time.perf_counter()
        self.active_started = self.started
        self.ended = None
        self.pending_timings = {}
        self.pending_step = 0
        self.task, self.call_task = None, None
        self.last_decision = 0.0
        self.last_submitted_seq = -1
        self.inflight = None
        self.applied_ids = set()
        self.warmup_info = None
        self.metadata = hardware()
        self.failure_streak = 0
        self.sample_manifest = None

    def summary(self):
        return {
            "id": self.id,
            "episode_id": self.episode,
            "created_at": self.created_at,
            "status": self.status,
            "error": self.error,
            "config": self.config.model_dump(),
            "metadata": self.metadata,
            "warmup": self.warmup_info,
            "execution": self.config.execution,
            "sample": self.sample_manifest,
            "metrics": self.metrics(),
        }

    def metrics(self):
        return {
            "counts": dict(self.counts),
            "provider_ms": percentiles(self.latencies),
            "end_to_end_ms": percentiles(self.e2e),
            "state_age_ms": percentiles(self.ages),
            "inference_ms": percentiles(self.inferences),
            "queue_ms": percentiles(self.queues),
            "overhead_ms": percentiles(self.overheads),
            "paint_ms": percentiles(self.paints),
            "decisions_per_second": len(self.latencies)
            / max(0.001, (self.ended or time.perf_counter()) - self.active_started),
            "quality": evaluate(self.business.results) if self.business else None,
            "score": self.current["state"].get("score") if self.current else None,
        }

    def view(self):
        return {
            **self.summary(),
            "snapshot": self.current,
            "events": list(self.recent),
            "last_result": self.last_result,
            "last_request": self.last_request,
            "rows": self.business.results if self.business else [],
        }

    async def emit(self, kind, **payload):
        self.seq += 1
        event = {
            "seq": self.seq,
            "run_id": self.id,
            "kind": kind,
            "elapsed_ms": (time.perf_counter() - self.started) * 1000,
            **payload,
        }
        self.counts[kind] += 1
        if kind != "snapshot":
            self.recent.append(event)
        await self.store.event(self.id, event)
        for subscriber in list(self.subscribers):
            if subscriber.full():
                # Tell slow readers to recover from durable history rather than hiding lost events.
                while not subscriber.empty():
                    subscriber.get_nowait()
                subscriber.put_nowait({"kind": "resync", "run_id": self.id})
            else:
                subscriber.put_nowait(event)

    async def start(self):
        await self.store.save_run(self.summary())
        self.task = asyncio.create_task(self._loop())

    async def _loop(self):
        try:
            await self.emit("preparing", message="Preparando proveedor y entorno")
            # One gate per provider; local model warmup cannot overlap another physical inference.
            async with self.gate:
                self.warmup_info = await self.adapter.warmup()
            if self.status == "stopped":
                return
            self.active_started = time.perf_counter()
            if self.config.scenario in GAMES:
                self.sim = Simulation(self.config.model_dump(), self.episode)
            else:
                items, self.sample_manifest = sample(
                    validate_dataset(self.config.dataset or fixtures(self.config.scenario)),
                    self.config.sample_size,
                    self.config.sampling,
                    self.config.seed,
                    self.config.difficulty,
                )
                self.business = Business(self.config.scenario, items, self.config.graph, self.config.options)
                await self._business_snapshot()
            self.status = "running"
            await self.emit("ready", warmup=self.warmup_info, sample=self.sample_manifest)
            while self.status in ("running", "paused"):
                if self.sim:
                    for item in self.sim.read():
                        kind = item.pop("kind")
                        if kind == "snapshot":
                            self.current = item
                            await self.emit("snapshot", **item)
                        elif kind == "applied":
                            self.e2e.append(item["end_to_end_ms"])
                            self.ages.append(item["age_ms"])
                            self.applied_ids.add(item["request_id"])
                            excluded = self.pending_timings.pop(item["request_id"], None)
                            if excluded is not None:
                                self.overheads.append(max(0, item["end_to_end_ms"] - excluded))
                            await self.emit(kind, **item)
                        else:
                            self.pending_timings.pop(item.get("request_id"), None)
                            await self.emit(kind, **item)
                    if self.status in ("running", "paused") and not self.sim.process.is_alive():
                        raise RuntimeError("El proceso de simulación terminó inesperadamente")
                if self.status == "stopped":
                    break
                if self.current and self.current["state"].get("done"):
                    self.status = "completed"
                    break
                if (
                    self.config.execution != "batch"
                    and time.perf_counter() - self.active_started >= self.config.max_seconds
                ):
                    self.status = "completed"
                    await self.emit("time_limit")
                    break
                if self.call_task and self.call_task.done():
                    await self.call_task
                    self.call_task = None
                if (
                    not self.paused
                    and self.current
                    and not self.call_task
                    and self.config.controller == "model"
                    and (self.config.mode == "realtime" or self.pending_step > 0)
                    and (
                        self.config.execution != "realtime"
                        or time.perf_counter() - self.last_decision >= 1 / self.config.decision_hz
                    )
                    and (
                        self.current["state_seq"] != self.last_submitted_seq
                        or self.business
                        or self.config.mode == "step"
                    )
                ):
                    if self.config.mode == "step":
                        self.pending_step -= 1
                    self.last_decision = time.perf_counter()
                    self.last_submitted_seq = self.current["state_seq"]
                    self.call_task = asyncio.create_task(self._decide(dict(self.current)))
                await asyncio.sleep(0.005)
        except Exception as exc:
            self.status, self.error = "failed", str(exc)
            await self.emit("failed", error=self.error)
        finally:
            self.ended = time.perf_counter()
            if self.call_task:
                # Let actual inference finish to preserve the one-physical-call invariant.
                await asyncio.gather(self.call_task, return_exceptions=True)
            if self.sim:
                await asyncio.to_thread(self.sim.close)
            await self.emit("finished", status=self.status, metrics=self.metrics())
            await self.store.save_run(self.summary())

    async def _business_snapshot(self):
        b = self.business
        self.current = {
            "episode_id": self.episode,
            "state_seq": b.seq,
            "captured_ns": time.perf_counter_ns(),
            "state": b.observe(),
            "questions": {k: q.model_dump() for k, q in b.questions().items()} if not b.done else {},
            "allowed_actions": [],
        }
        await self.emit("snapshot", **self.current)

    async def _decide(self, snapshot):
        accepted = time.perf_counter_ns()
        # Business inputs don't expire merely because they sat in an inbox.
        if self.business:
            snapshot["captured_ns"] = accepted
        request = DecisionRequest(
            run_id=self.id,
            episode_id=self.episode,
            state_seq=snapshot["state_seq"],
            schema_id=self.config.scenario + "/1",
            state=snapshot["state"],
            questions=snapshot["questions"],
            allowed_actions=snapshot["allowed_actions"],
            budget_ms=self.config.budget_ms
            if self.config.execution == "realtime"
            else self.config.request_timeout_ms,
            max_state_age_ms=self.config.max_state_age_ms
            if self.config.execution == "realtime"
            else self.config.request_timeout_ms,
        )
        rid = request.request_id
        self.last_request = request.model_dump()
        await self.emit("accepted", request=self.last_request, request_id=rid)
        await self.emit("queued", request_id=rid)
        deadline = accepted + request.budget_ms * 1_000_000
        lock_acquired = False
        try:
            try:
                await asyncio.wait_for(
                    self.gate.acquire(), max(0.001, (deadline - time.perf_counter_ns()) / 1e9)
                )
                lock_acquired = True
            except TimeoutError:
                await self.emit("expired", request_id=rid, stage="queue")
                if self.business and self.status == "running":
                    await self._failed_item("Tiempo de espera en cola agotado", 0)
                return
            started = time.perf_counter_ns()
            queue_ms = (started - accepted) / 1e6
            self.queues.append(queue_ms)
            if started >= deadline or self.status != "running" or self.paused:
                await self.emit("expired", request_id=rid, stage="before_call")
                return
            await self.emit("started", request_id=rid, queue_ms=queue_ms)
            future = asyncio.create_task(self.adapter.decide(request))
            self.inflight = rid
            expired = False
            try:
                result = await asyncio.wait_for(
                    asyncio.shield(future), max(0.001, (deadline - time.perf_counter_ns()) / 1e9)
                )
            except TimeoutError:
                expired = True
                await self.emit("expired", request_id=rid, stage="provider")
                result = await future
            ended = time.perf_counter_ns()
            provider_ms = (ended - started) / 1e6
            self.latencies.append(provider_ms)
            if result.timings.get("inference_ms") is not None:
                self.inferences.append(result.timings["inference_ms"])
            result.timings.update(provider_ms=provider_ms, queue_ms=queue_ms)
            self.last_result = result.model_dump()
            await self.emit("completed", request_id=rid, result=self.last_result, late=expired)
            self.failure_streak = 0
            if self.status != "running" or self.paused:
                await self.emit("rejected", request_id=rid, reason="run_not_active")
                return
            if (
                expired
                or ended > deadline
                or (
                    self.config.execution == "realtime"
                    and ended - snapshot["captured_ns"] > request.max_state_age_ms * 1e6
                )
            ):
                if not expired:
                    await self.emit("expired", request_id=rid, stage="state_age")
                if self.business:
                    await self._failed_item("Tiempo de espera del proveedor agotado", provider_ms)
                return
            if self.business:
                previous_count = len(self.business.results)
                self.business.apply(self.last_result)
                self.e2e.append((time.perf_counter_ns() - accepted) / 1e6)
                self.overheads.append(max(0, self.e2e[-1] - provider_ms - queue_ms))
                self.applied_ids.add(rid)
                await self.emit(
                    "applied",
                    request_id=rid,
                    answers=self.last_result["answers"],
                    row=self.business.results[-1] if len(self.business.results) > previous_count else None,
                    end_to_end_ms=self.e2e[-1],
                )
                await self._business_snapshot()
            else:
                self.pending_timings[rid] = provider_ms + queue_ms
                self.sim.send(
                    {
                        "kind": "action",
                        "action": result.answers["action"].value,
                        "request_id": rid,
                        "episode_id": self.episode,
                        "state_seq": snapshot["state_seq"],
                        "captured_ns": snapshot["captured_ns"],
                        "accepted_ns": accepted,
                        "deadline_ns": deadline,
                        "valid_until_ns": snapshot["captured_ns"] + request.max_state_age_ms * 1_000_000
                        if self.config.execution == "realtime"
                        else deadline,
                    }
                )
        except Exception as exc:
            self.failure_streak += 1
            await self.emit("failed", request_id=rid, error=str(exc))
            if self.business and self.status == "running":
                await self._failed_item(str(exc), (time.perf_counter_ns() - accepted) / 1e6)
            elif self.failure_streak >= 3:
                self.error, self.status = str(exc), "failed"
        finally:
            # Retry an unchanged turn after expiry/failure, but wait for the simulation
            # acknowledgement when a successful action is already queued.
            if self.config.scenario == "tic-tac-toe" and rid not in self.pending_timings:
                if rid not in self.applied_ids:
                    self.last_submitted_seq = -1
            self.inflight = None
            if lock_acquired:
                self.gate.release()

    async def _failed_item(self, error, latency_ms):
        self.business.fail(error, latency_ms)
        await self.emit("case_failed", row=self.business.results[-1], error=error)
        await self._business_snapshot()

    async def control(self, command, action=None):
        if command == "stop":
            if self.status not in ("preparing", "running", "paused"):
                return
            self.status = "stopped"
            self.pending_step = 0
            # Stop physics immediately, even while a physical inference is still finishing.
            if self.sim:
                self.sim.stopping.set()
            await self.emit("stopped")
        elif self.status not in ("running", "paused"):
            raise ValueError("La ejecución no está activa")
        elif command in ("pause", "resume"):
            self.paused = command == "pause"
            self.status = "paused" if self.paused else "running"
            if self.sim:
                self.sim.send({"kind": "pause", "value": self.paused})
            await self.emit(command)
        elif command == "step":
            if self.config.mode != "step":
                raise ValueError("Usa el modo paso a paso")
            self.pending_step = min(1, self.pending_step + 1)
        elif command == "action":
            if self.config.controller != "human" or not self.sim or not self.current:
                raise ValueError("El control humano requiere un juego activo")
            now = time.perf_counter_ns()
            self.sim.send(
                {
                    "kind": "action",
                    "request_id": uuid4().hex,
                    "action": action,
                    "episode_id": self.episode,
                    "state_seq": self.current["state_seq"],
                    "captured_ns": now,
                    "accepted_ns": now,
                    "deadline_ns": now + 1_000_000_000,
                    "valid_until_ns": now + 1_000_000_000,
                }
            )
        else:
            raise ValueError("Comando desconocido")

    async def stop(self):
        if self.status in ("preparing", "running", "paused"):
            await self.control("stop")
        if self.task:
            await self.task
