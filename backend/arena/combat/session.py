"""Match lifecycle and independent asynchronous controllers, outside the physics process."""

import asyncio
import copy
import time
from collections import Counter
from datetime import UTC, datetime
from uuid import uuid4

from arena.metrics import percentiles
from arena.protocol import DecisionRequest

from .content import CONTENT_VERSION, RULES_VERSION
from .engine import World
from .observation import observe
from .worker import CombatProcess


class Match:
    def __init__(self, config, registry, store):
        self.id = uuid4().hex
        self.config = config.model_copy(deep=True)
        self.registry = registry
        self.store = store
        self.status = "preparing"
        self.error = None
        self.seq = 0
        self.snapshot = None
        self.packet = None
        self.process = None
        self.task = None
        self.created_at = datetime.now(UTC).isoformat()
        self.subscribers = set()
        self.paused = False
        self.active_time = 0.0
        self.calls = [None, None]
        self.last_call = [0.0, 0.0]
        self.last_epoch = [None, None]
        # An action sent but not yet acked, or acked but not yet in a snapshot, makes the
        # latest packet stale for that slot: querying on it wastes a call on a past state.
        self.awaiting = [None, None]
        self.unsynced = [False, False]
        self.stats = [
            dict(
                counts=Counter(),
                latencies=[],
                last_request=None,
                last_result=None,
                error=None,
                failures=0,
                last_useful=time.perf_counter(),
                model=None,
            )
            for _ in (0, 1)
        ]
        self.profiles = [
            None if s.controller == "human" else registry.profiles[s.model_profile_id].model_dump()
            for s in config.players
        ]
        self.sealed = []
        self.warmup = []
        self.last_snapshot_saved = 0
        self.last_metrics = 0

    def view(self):
        players = []
        for i, (slot, s) in enumerate(zip(self.config.players, self.stats, strict=True)):
            players.append(
                dict(
                    **slot.model_dump(),
                    counts=dict(s["counts"]),
                    latency=percentiles(s["latencies"]),
                    last_request=s["last_request"],
                    last_result=s["last_result"],
                    error=s["error"],
                    actual_model=s["model"],
                    pending=bool(self.calls[i] and not self.calls[i].done()),
                )
            )
        return dict(
            id=self.id,
            created_at=self.created_at,
            status=self.status,
            error=self.error,
            config=self.config.model_dump(),
            players=players,
            state=self.snapshot,
            rules_version=RULES_VERSION,
            content_version=CONTENT_VERSION,
            warmup=self.warmup,
            active_seconds=round(self.active_time, 2),
            profiles=[
                None if p is None else {k: v for k, v in p.items() if k != "credential_env"}
                for p in self.profiles
            ],
        )

    async def emit(self, kind, save=True, **data):
        self.seq += 1
        event = dict(seq=self.seq, kind=kind, match_id=self.id, at=time.time(), **data)
        if save:
            await self.store.event(self.id, event)
        for subscriber in list(self.subscribers):
            try:
                subscriber.put_nowait(event)
            except asyncio.QueueFull:
                while not subscriber.empty():
                    subscriber.get_nowait()
                subscriber.put_nowait(dict(kind="resync", seq=self.seq))

    async def start(self):
        await self.store.save_run(self.view())
        self.task = asyncio.create_task(self.loop())

    async def loop(self):
        try:
            warmed = set()
            for i, slot in enumerate(self.config.players):
                if self.status == "stopped":
                    return
                if slot.controller == "human" or slot.model_profile_id in warmed:
                    continue
                adapter = self.registry.adapters[slot.model_profile_id]
                async with self.registry.gates[slot.model_profile_id]:
                    info = await adapter.warmup()
                    if hasattr(adapter, "preflight"):
                        payloads = []
                        for character in ("ember", "flux", "terra", "nyx"):
                            cfg = self.config.model_dump()
                            cfg["players"][i]["fighter_id"] = character
                            w = World(cfg)
                            w.phase = "active"
                            w.fighters[i].energy = 10000
                            payload = observe(w, i)
                            payloads.append(dict(state=payload["state"], questions=payload["questions"]))
                            w.begin_clash()
                            payload = observe(w, i)
                            payloads.append(dict(state=payload["state"], questions=payload["questions"]))
                        info["preflight"] = await adapter.preflight(payloads)
                    self.warmup.append(dict(profile=slot.model_profile_id, **info))
                warmed.add(slot.model_profile_id)
            if self.status == "stopped":
                return
            self.process = CombatProcess(self.config.model_dump())
            self.status = "running"
            last = time.perf_counter()
            for s in self.stats:
                s["last_useful"] = last
            await self.emit("ready", warmup=self.warmup)
            while self.status in ("running", "paused"):
                now = time.perf_counter()
                if self.status == "running":
                    self.active_time += now - last
                last = now
                for packet in self.process.read():
                    kind = packet.pop("kind")
                    if kind == "snapshot":
                        self.packet = packet
                        self.snapshot = packet["state"]
                        self.unsynced = [False, False]
                        save = now - self.last_snapshot_saved >= 0.1 or self.snapshot["done"]
                        if save:
                            self.last_snapshot_saved = now
                        await self.emit("snapshot", save=save, state=self.snapshot)
                    else:
                        if kind in ("input_ack", "buffer_applied"):
                            i = int(packet["player_id"][1]) - 1
                            reason = packet.get("reason")
                            self.stats[i]["counts"][
                                "buffered" if reason == "buffered" else "rejected" if reason else "applied"
                            ] += 1
                        if kind in ("applied", "rejected"):
                            i = int(packet["player_id"][1]) - 1
                            if packet.get("request_id") == self.awaiting[i]:
                                self.awaiting[i] = None
                                self.unsynced[i] = True
                            self.stats[i]["counts"][kind] += 1
                            if kind == "applied":
                                self.stats[i]["last_useful"] = now
                        if kind == "combat" and packet["event"]["kind"] in ("clash_pulse", "clash_end"):
                            pending, self.sealed = self.sealed, []
                            for event in pending:
                                await self.publish_decision(**event)
                        await self.emit(kind, **packet)
                if self.status == "stopped":
                    break
                if not self.process.process.is_alive():
                    raise RuntimeError("El proceso de combate se detuvo")
                if self.snapshot and self.snapshot["done"]:
                    self.status = "completed"
                    break
                if self.active_time >= self.config.max_seconds:
                    self.status = "completed"
                    await self.emit("time_limit")
                    break
                for i, slot in enumerate(self.config.players):
                    if self.calls[i] and self.calls[i].done():
                        await self.calls[i]
                        self.calls[i] = None
                    if (
                        self.status != "running"
                        or not self.packet
                        or self.packet.get("paused")
                        or slot.controller == "human"
                        or self.calls[i]
                        or self.awaiting[i]
                        or self.unsynced[i]
                    ):
                        continue
                    view = self.packet["views"][i]
                    if not view["actions"]:
                        self.stats[i]["last_useful"] = now
                        continue
                    if now - self.stats[i]["last_useful"] > 5 and slot.controller == "model":
                        await self.pause_error(
                            f"P{i + 1}: cinco segundos sin una acción útil. Revisa la latencia o el perfil."
                        )
                        break
                    phase = self.snapshot["phase"]
                    epoch = self.snapshot["epoch"]
                    delay = 0.8 if self.config.pace == "equal_windows" else 1 / self.config.decision_hz
                    urgent = phase in ("clash", "finish") and self.last_epoch[i] != epoch
                    if now - self.last_call[i] >= delay or urgent:
                        self.last_call[i] = now
                        self.last_epoch[i] = epoch
                        self.calls[i] = asyncio.create_task(self.decide(i, copy.deepcopy(self.packet)))
                if now - self.last_metrics >= 0.5:
                    self.last_metrics = now
                    await self.emit("metrics", save=False, players=self.view()["players"], status=self.status)
                await asyncio.sleep(0.004)
        except Exception as exc:
            self.status = "failed"
            self.error = str(exc)
            await self.emit("error", error=self.error)
        finally:
            try:
                await self.emit("status", status=self.status, error=self.error)
            finally:
                # Cleanup must survive a dead store writer, or the combat process leaks.
                if self.process:
                    self.process.stopping.set()
                await asyncio.gather(*(c for c in self.calls if c), return_exceptions=True)
                if self.process:
                    await asyncio.to_thread(self.process.close)
            for event in self.sealed:
                await self.publish_decision(**event)
            self.sealed = []
            await self.emit("finished", match=self.view())
            await self.store.save_run(self.view())

    async def publish_decision(self, i, request, result, latency, late):
        s = self.stats[i]
        s["last_request"] = request
        s["last_result"] = result
        await self.emit(
            "decision", player_id=f"p{i + 1}", request=request, result=result, latency_ms=latency, late=late
        )

    async def decide(self, i, packet):
        slot = self.config.players[i]
        s = self.stats[i]
        view = packet["views"][i]
        adapter = self.registry.adapters[slot.model_profile_id]
        gate = self.registry.gates[slot.model_profile_id]
        now = time.perf_counter_ns()
        epoch = packet["state"]["epoch"]
        phase = packet["state"]["phase"]
        budget = self.config.budget_ms
        if phase == "clash":
            budget = max(1, int(packet["state"]["clash"]["left"] / 60 * 1000) - 10)
        if phase == "finish":
            budget = max(1, int(packet["state"]["phase_left"] / 60 * 1000) - 10)
        request = DecisionRequest(
            run_id=self.id,
            episode_id=f"{self.id}:{epoch}",
            state_seq=packet["state"]["tick"],
            schema_id="combat/1",
            state=view["state"],
            questions=view["questions"],
            allowed_actions=view["actions"],
            budget_ms=max(10, budget),
            max_state_age_ms=self.config.max_age_ms,
        )
        deadline = now + budget * 1_000_000
        s["counts"]["accepted"] += 1
        await self.emit("thinking", player_id=f"p{i + 1}", request_id=request.request_id)
        acquired = False
        try:
            await asyncio.wait_for(gate.acquire(), max(0.001, (deadline - time.perf_counter_ns()) / 1e9))
            acquired = True
            if self.status != "running" or self.paused or self.snapshot["epoch"] != epoch:
                return
            start = time.perf_counter_ns()
            future = asyncio.create_task(adapter.decide(request))
            late = False
            try:
                result = await asyncio.wait_for(asyncio.shield(future), max(0.001, (deadline - start) / 1e9))
            except TimeoutError:
                late = True
                s["counts"]["expired"] += 1
                await self.emit("expired", player_id=f"p{i + 1}", request_id=request.request_id)
                result = await future
            end = time.perf_counter_ns()
            # Free the provider before pacing sleeps so a shared gate never idles.
            gate.release()
            acquired = False
            latency = (end - start) / 1e6
            s["latencies"].append(latency)
            s["latencies"] = s["latencies"][-10000:]
            s["model"] = result.model
            s["failures"] = 0
            s["error"] = None
            s["counts"]["completed"] += 1
            event = dict(
                i=i, request=request.model_dump(), result=result.model_dump(), latency=latency, late=late
            )
            if phase == "clash" and self.snapshot and self.snapshot["epoch"] == epoch:
                self.sealed.append(event)
            else:
                await self.publish_decision(**event)
            if self.config.pace == "equal_windows" and phase == "active":
                await asyncio.sleep(max(0, (now + 800_000_000 - time.perf_counter_ns()) / 1e9))
            if self.status != "running" or self.paused or self.snapshot["epoch"] != epoch:
                s["counts"]["rejected"] += 1
                await self.emit(
                    "rejected", player_id=f"p{i + 1}", request_id=request.request_id, reason="context_changed"
                )
                return
            expired = late or end > deadline or end - packet["captured_ns"] > self.config.max_age_ms * 1e6
            if expired:
                if not late:
                    s["counts"]["expired"] += 1
                return
            self.process.send(
                dict(
                    kind="action",
                    player=i,
                    epoch=epoch,
                    action=result.answers["action"].value,
                    source="baseline" if slot.controller == "baseline" else "model",
                    request_id=request.request_id,
                    captured_ns=packet["captured_ns"],
                    deadline_ns=(
                        now + 850_000_000
                        if self.config.pace == "equal_windows" and phase == "active"
                        else deadline
                    ),
                )
            )
            # No await since send: the ack cannot have been read yet.
            self.awaiting[i] = request.request_id
        except TimeoutError:
            s["counts"]["expired"] += 1
            await self.emit("expired", player_id=f"p{i + 1}", request_id=request.request_id)
        except Exception as exc:
            s["failures"] += 1
            s["counts"]["errors"] += 1
            s["error"] = str(exc)
            await self.emit("provider_error", player_id=f"p{i + 1}", error=str(exc))
            if s["failures"] >= 3 and self.status == "running":
                await self.pause_error(f"P{i + 1}: {exc}")
        finally:
            if acquired:
                gate.release()

    async def pause_error(self, message):
        self.error = message
        await self.control("pause")
        await self.emit("error", error=message)

    async def control(self, command):
        if command == "stop":
            if self.status not in ("preparing", "running", "paused"):
                return
            self.status = "stopped"
            self.paused = True
            if self.process:
                self.process.stopping.set()
        elif command in ("pause", "resume"):
            if self.status not in ("running", "paused"):
                raise ValueError("La partida no está activa")
            self.paused = command == "pause"
            self.status = "paused" if self.paused else "running"
            if command == "resume":
                self.error = None
                for s in self.stats:
                    s["last_useful"] = time.perf_counter()
                    s["failures"] = 0
            self.process.send(dict(kind=command))
        elif command in ("reset", "step"):
            if self.config.mode != "training" or self.status not in ("running", "paused"):
                raise ValueError("Disponible sólo en entrenamiento activo")
            self.process.send(dict(kind=command))
        elif command == "skip":
            if self.process and self.status in ("running", "paused"):
                self.process.send(dict(kind="skip"))
        await self.emit("status", status=self.status, error=self.error)

    async def stop(self):
        await self.control("stop")
        if self.task:
            await self.task

    def human(self, player, action, seq, release=False, input_stream="default"):
        if player not in (0, 1) or self.config.players[player].controller != "human":
            raise ValueError("Slot no humano")
        if self.status != "running" or not self.process:
            return
        if release:
            self.process.send(dict(kind="release", player=player))
            return
        self.process.send(
            dict(
                kind="action",
                player=player,
                action=action,
                input_seq=seq,
                input_stream=input_stream,
                source="human",
            )
        )
