import asyncio

from arena.protocol import normalize
from test_runtime import launch, runtime  # noqa: F401


class Heavy:
    """Slower than the 3 Hz pacing, so a finished call can re-fire at once."""

    def __init__(self):
        self.requests = []

    async def warmup(self):
        return {"ready": True}

    async def decide(self, req):
        self.requests.append(req)
        await asyncio.sleep(0.4)
        action = "heavy" if "heavy" in req.allowed_actions else req.allowed_actions[0]
        return normalize({"answers": {"action": {"type": "choice", "choice": action}}}, req, "test")

    async def close(self):
        pass


async def test_next_request_waits_for_snapshot_with_applied_action(runtime):  # noqa: F811
    adapter = Heavy()
    m = await launch(runtime, adapter, max_seconds=5)
    applied = []
    events = asyncio.Queue()
    m.subscribers.add(events)
    await m.task
    while not events.empty():
        e = events.get_nowait()
        if e["kind"] == "applied":
            applied.append((e["player_id"], e["tick"], e["action"]))
    assert any(a == "heavy" for *_, a in applied)
    seen = {(r.state["player_id"], r.state_seq) for r in adapter.requests}
    for pid, tick, action in applied:
        # A stale packet predates the heavy (tick <= ack tick); a synced one shows it until it ends.
        if action == "heavy":
            assert not any((pid, t) in seen for t in range(tick - 2, tick + 6)), (pid, tick)
