"""Independent 60Hz authoritative process; IO/model latency never advances physics."""

import multiprocessing as mp
import queue
import time

from .engine import World
from .observation import observe


def worker(config, incoming, outgoing, stopping):
    world = World(config)
    paused = False
    last_event = 0
    next_tick = time.perf_counter()
    buffered = {}
    last_input = {}
    publish = 0

    def emit(data):
        try:
            outgoing.put_nowait(data)
        except queue.Full:
            if data["kind"] != "snapshot":
                outgoing.put(data, timeout=0.2)

    def snapshot():
        emit(
            dict(
                kind="snapshot",
                state=world.snapshot(),
                views=[observe(world, i) for i in (0, 1)],
                captured_ns=time.perf_counter_ns(),
                paused=paused,
            )
        )

    snapshot()
    while not stopping.is_set():
        for _ in range(64):
            try:
                cmd = incoming.get_nowait()
            except queue.Empty:
                break
            kind = cmd["kind"]
            if kind in ("pause", "resume"):
                paused = kind == "pause"
                world.epoch += 1
                world.neutral()
                buffered.clear()
                emit(dict(kind="controlled", command=kind, epoch=world.epoch))
                snapshot()
            elif kind == "reset" and config["mode"] == "training":
                epoch = world.epoch + 1
                world = World(config)
                world.epoch = epoch
                buffered.clear()
                last_event = 0
                snapshot()
            elif kind == "skip" and world.phase in ("cinematic", "finish", "finisher"):
                world.phase_left = 1
                if paused:
                    world.step()
            elif kind == "step" and paused and config["mode"] == "training":
                world.step()
                snapshot()
            elif kind == "release":
                world.neutral(cmd["player"])
            elif kind == "action":
                now = time.perf_counter_ns()
                i = cmd["player"]
                stream = (i, cmd.get("input_stream", "default"))
                reason = None
                if paused:
                    reason = "paused"
                elif world.done:
                    reason = "finished"
                elif cmd.get("epoch", world.epoch) != world.epoch:
                    reason = "context_changed"
                elif now > cmd.get("deadline_ns", now + 1):
                    reason = "expired"
                elif cmd.get("source") == "human" and cmd["input_seq"] <= last_input.get(stream, -1):
                    reason = "duplicate_input"
                else:
                    if cmd.get("source") == "human":
                        last_input[stream] = cmd["input_seq"]
                    if not world.apply(i, cmd["action"], cmd.get("source", "model"), cmd.get("request_id")):
                        if cmd.get("source") == "human" and world.phase == "active":
                            buffered[i] = (world.tick + 6, cmd)
                            reason = "buffered"
                        else:
                            reason = "illegal_action"
                emit(
                    dict(
                        kind="input_ack"
                        if cmd.get("source") == "human"
                        else "rejected"
                        if reason
                        else "applied",
                        player_id=f"p{i + 1}",
                        action=None if world.phase == "clash" else cmd["action"],
                        request_id=cmd.get("request_id"),
                        input_seq=cmd.get("input_seq"),
                        reason=reason,
                        tick=world.tick,
                        epoch=world.epoch,
                        age_ms=(now - cmd.get("captured_ns", now)) / 1e6,
                    )
                )
        now = time.perf_counter()
        if now >= next_tick:
            steps = min(5, int((now - next_tick) * 60) + 1)
            for _ in range(steps):
                if not paused:
                    for i, (until, cmd) in list(buffered.items()):
                        if world.tick > until:
                            buffered.pop(i)
                        elif world.apply(i, cmd["action"], "human", cmd.get("request_id")):
                            buffered.pop(i)
                            emit(
                                dict(
                                    kind="buffer_applied",
                                    player_id=f"p{i + 1}",
                                    input_seq=cmd["input_seq"],
                                    tick=world.tick,
                                    action=cmd["action"],
                                )
                            )
                    world.step()
                next_tick += 1 / 60
            if now - next_tick > 0.2:
                next_tick = now
        for event in world.events:
            if event["seq"] > last_event:
                emit(dict(kind="combat", event=event))
                last_event = event["seq"]
        if now - publish >= 1 / 30:
            snapshot()
            publish = now
        stopping.wait(0.002)


class CombatProcess:
    def __init__(self, config):
        ctx = mp.get_context("spawn")
        self.incoming = ctx.Queue(128)
        self.outgoing = ctx.Queue(512)
        self.stopping = ctx.Event()
        self.process = ctx.Process(
            target=worker, args=(config, self.incoming, self.outgoing, self.stopping), daemon=True
        )
        self.process.start()

    def send(self, cmd):
        self.incoming.put_nowait(cmd)

    def read(self):
        result = []
        for _ in range(512):
            try:
                result.append(self.outgoing.get_nowait())
            except queue.Empty:
                break
        return result

    def close(self):
        self.stopping.set()
        self.process.join(2)
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(1)
        self.incoming.cancel_join_thread()
        self.outgoing.cancel_join_thread()
        self.incoming.close()
        self.outgoing.close()
        self.process.close()
