"""Run a real-time reference match for 30 minutes, with resource and lifecycle assertions."""

import asyncio
import json
import sys
import time
from pathlib import Path

from arena.combat.profiles import Registry
from arena.combat.protocol import MatchConfig
from arena.combat.session import Match
from arena.storage import Store


async def main(seconds=1800):
    registry = Registry()
    store = Store("/tmp/eclipse-soak")
    store.start()
    config = MatchConfig(mode="training", max_seconds=seconds)
    match = Match(config, registry, store)
    await match.start()
    started = time.monotonic()
    samples = []
    while not match.task.done():
        await asyncio.sleep(10)
        view = match.view()
        state = view["state"]
        if state:
            assert all(
                0 <= f["energy"] <= 100 and 0 <= f["guard"] <= 100 and -10 <= f["x"] <= 10
                for f in state["fighters"]
            )
            samples.append(
                {
                    "seconds": round(time.monotonic() - started),
                    "tick": state["tick"],
                    "status": view["status"],
                    "rss_kb": int(Path("/proc/self/status").read_text().split("VmRSS:")[1].split()[0]),
                    "counts": [p["counts"] for p in view["players"]],
                }
            )
        if match.status in ("failed", "paused"):
            await match.stop()
            raise RuntimeError(match.error or match.status)
        Path("/tmp/eclipse-soak-progress.json").write_text(json.dumps(samples, indent=2))
    await match.task
    await registry.close()
    await store.close()
    Path("/tmp/eclipse-soak-result.json").write_text(
        json.dumps(
            {"elapsed": time.monotonic() - started, "match": match.view(), "samples": samples}, indent=2
        )
    )
    print(
        json.dumps(
            {"status": match.status, "seconds": round(time.monotonic() - started), "samples": len(samples)}
        )
    )


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 1800))
