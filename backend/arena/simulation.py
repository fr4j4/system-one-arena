"""An authoritative 60 Hz simulation in an independent spawned process."""

import multiprocessing as mp
import queue
import time

from arena.scenarios.games import Game


def simulation_main(config, episode, incoming, outgoing, stopping):
    game = Game(config["scenario"], config["seed"], config["options"])
    seq, paused, hold_until = 0, False, 0
    next_tick = last_publish = time.perf_counter()
    seen = set()

    def emit(event):
        try:
            outgoing.put(event, timeout=0.2)
        except queue.Full:
            # Snapshots are replaceable. Commands are retried by the coordinator via state refresh.
            pass

    def snapshot():
        return {
            "kind": "snapshot",
            "episode_id": episode,
            "state_seq": seq,
            "captured_ns": time.perf_counter_ns(),
            "state": game.observe(config["representation"] == "enriched"),
            "allowed_actions": game.legal_actions(),
            "questions": {k: q.model_dump() for k, q in game.questions().items()} if not game.done else {},
        }

    emit(snapshot())
    while not stopping.is_set():
        now = time.perf_counter()
        for _ in range(64):
            try:
                cmd = incoming.get_nowait()
            except queue.Empty:
                break
            if cmd["kind"] == "pause":
                paused = cmd["value"]
                if paused:
                    game.neutral()
            elif cmd["kind"] == "action":
                ns = time.perf_counter_ns()
                reason = None
                if cmd["request_id"] in seen:
                    reason = "duplicate"
                elif cmd["episode_id"] != episode:
                    reason = "episode_mismatch"
                elif paused:
                    reason = "paused"
                elif ns > cmd["deadline_ns"] or ns > cmd["valid_until_ns"]:
                    reason = "expired"
                elif cmd["state_seq"] > seq:
                    reason = "future_state"
                elif game.name == "tic-tac-toe" and cmd["state_seq"] != seq:
                    reason = "superseded"
                elif not game.apply(cmd["action"]):
                    reason = "illegal_action"
                seen.add(cmd["request_id"])
                if not reason:
                    hold_until = cmd["valid_until_ns"]
                    if config["mode"] == "step":
                        for _ in range(12):
                            game.tick(1 / 60 * config["speed"])
                    seq += 1
                emit(
                    {
                        "kind": "rejected" if reason else "applied",
                        "request_id": cmd["request_id"],
                        "reason": reason,
                        "state_seq": seq,
                        "action": cmd["action"],
                        "age_ms": (ns - cmd["captured_ns"]) / 1e6,
                        "end_to_end_ms": (ns - cmd["accepted_ns"]) / 1e6,
                    }
                )
                emit(snapshot())
        if now >= next_tick:
            # Never fast-forward a stalled process by an unbounded number of steps.
            steps = min(5, int((now - next_tick) * 60) + 1)
            for _ in range(steps):
                if not paused and config["mode"] == "realtime" and not game.done:
                    if time.perf_counter_ns() > hold_until:
                        game.neutral()
                    game.tick(config["speed"] / 60)
                    seq += 1
            next_tick = now + 1 / 60
        if now - last_publish >= 0.05:
            emit(snapshot())
            last_publish = now
        stopping.wait(0.002)


class Simulation:
    def __init__(self, config, episode):
        ctx = mp.get_context("spawn")
        self.incoming, self.outgoing = ctx.Queue(maxsize=64), ctx.Queue(maxsize=256)
        self.stopping = ctx.Event()
        self.process = ctx.Process(
            target=simulation_main,
            args=(config, episode, self.incoming, self.outgoing, self.stopping),
            daemon=True,
        )
        self.process.start()

    def send(self, command):
        self.incoming.put_nowait(command)

    def read(self):
        events = []
        for _ in range(256):
            try:
                events.append(self.outgoing.get_nowait())
            except queue.Empty:
                break
        return events

    def close(self):
        self.stopping.set()
        self.process.join(timeout=2)
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout=1)
        self.incoming.close()
        self.outgoing.close()
        self.incoming.join_thread()
        self.outgoing.join_thread()
        self.process.close()
        # Release named semaphore owners while the resource tracker is still alive.
        self.incoming = self.outgoing = self.stopping = None
