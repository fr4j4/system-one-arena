"""Explicit integration smoke; reads credentials only from server .env."""

import asyncio
import json
import sys
import time
from pathlib import Path

from arena.combat.engine import World
from arena.combat.observation import observe
from arena.combat.profiles import Registry
from arena.combat.protocol import MatchConfig
from arena.protocol import DecisionRequest
from dotenv import load_dotenv


async def main(provider):
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    registry = Registry()
    adapter = registry.adapters[provider]
    reports = []
    try:
        print(json.dumps({"warmup": await adapter.warmup()}), flush=True)
        for character in ("ember", "flux", "terra", "nyx"):
            world = World(MatchConfig().model_dump())
            world.fighters[0].character = character
            world.fighters[0].energy = 10000
            world.phase = "active"
            for phase in ("active", "clash", "finish"):
                if phase == "clash":
                    world.begin_clash()
                if phase == "finish":
                    world.phase = "finish"
                    world.winner = "p1"
                view = observe(world, 0)
                req = DecisionRequest(
                    run_id="integration",
                    episode_id=character,
                    state_seq=world.tick,
                    schema_id="combat/1",
                    state=view["state"],
                    questions=view["questions"],
                    allowed_actions=view["actions"],
                    budget_ms=800,
                    max_state_age_ms=1000,
                )
                start = time.perf_counter()
                result = await adapter.decide(req)
                elapsed = (time.perf_counter() - start) * 1000
                assert result.answers["action"].value in view["actions"]
                row = {
                    "fighter": character,
                    "phase": phase,
                    "action": result.answers["action"].value,
                    "ms": round(elapsed, 1),
                    "model": result.model,
                }
                reports.append(row)
                print(json.dumps(row), flush=True)
    finally:
        await registry.close()
        Path(f"/tmp/eclipse-{provider}-integration.json").write_text(json.dumps(reports, indent=2))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
