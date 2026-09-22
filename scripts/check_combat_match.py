"""End-to-end provider match smoke. Optional slow CPU diagnostic is explicitly labelled."""

import asyncio
import json
import sys
from pathlib import Path

from arena.combat.profiles import Registry
from arena.combat.protocol import MatchConfig, Slot
from arena.combat.session import Match
from arena.storage import Store
from dotenv import load_dotenv


async def main(provider):
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    registry = Registry()
    store = Store("/tmp/eclipse-real-" + provider)
    store.start()
    config = MatchConfig(
        players=[
            Slot(controller="model", model_profile_id=provider),
            Slot(fighter_id="flux", model_profile_id="aggressive"),
        ],
        max_seconds=20,
    )
    if provider == "laya":
        config.budget_ms = 5000
        config.max_age_ms = 6000
    match = Match(config, registry, store)
    await match.start()
    try:
        while not match.task.done():
            await asyncio.sleep(0.25)
            if match.status == "paused":
                await match.stop()
        await match.task
        view = match.view()
        report = {k: view[k] for k in ("status", "error", "active_seconds", "warmup")}
        report["timing"] = "slow CPU diagnostic 5000ms" if provider == "laya" else "native 800ms"
        report["players"] = [
            {
                k: p[k]
                for k in ("controller", "model_profile_id", "counts", "latency", "error", "actual_model")
            }
            for p in view["players"]
        ]
        report["fighters"] = [
            {"character": f["character"], "health": f["health"], "stats": f["stats"]}
            for f in (view["state"] or {}).get("fighters", [])
        ]
        Path("/tmp/eclipse-" + provider + "-match.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
    finally:
        await match.stop()
        await registry.close()
        await store.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
