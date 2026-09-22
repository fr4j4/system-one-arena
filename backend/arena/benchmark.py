"""Paired fixed-state and independent-episode evaluations, separate from interactive runs."""

import asyncio
import copy
import time
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import Field

from arena.metrics import evaluate, hardware, percentiles, temperature_scale
from arena.protocol import DecisionRequest, RunConfig, StrictModel
from arena.runtime import GAMES, Run
from arena.scenarios.business import Business
from arena.scenarios.games import Game, reference_action


class BenchmarkConfig(StrictModel):
    scenario: str = "snake"
    providers: list[str] = Field(default=["reference", "simulated"], min_length=1, max_length=4)
    mode: str = "corpus"
    warmup: int = Field(default=20, ge=0, le=100)
    samples: int = Field(default=500, ge=1, le=10000)
    episodes: int = Field(default=30, ge=1, le=100)
    episode_seconds: int = Field(default=30, ge=1, le=180)
    seed: int = Field(default=42, ge=0)
    budget_ms: int = Field(default=100, ge=10, le=60000)
    dataset: list[dict] | None = None
    options: dict = {}


def corpus(config):
    if config.scenario in GAMES:
        game = Game(config.scenario, config.seed, config.options)
        items = []
        seed = config.seed
        for _ in range(config.samples):
            if game.done:
                seed += 1
                game = Game(config.scenario, seed, config.options)
            actions = game.legal_actions()
            state = game.observe()
            action = reference_action(state, actions)
            items.append(
                {
                    "state": state,
                    "questions": game.questions(),
                    "allowed_actions": actions,
                    "expected": {"action": action},
                }
            )
            game.apply(action)
            for _ in range(12):
                game.tick(1 / 60)
        return items
    business = Business(config.scenario, config.dataset, options=config.options)
    items = []
    # Hierarchical/workflow decisions use corpus captured along the reference path.
    while len(items) < config.samples and not business.done:
        questions = business.questions()
        source = business.items[business.index]
        expected = source.get("expected", {})
        items.append(
            {"state": business.observe(), "questions": questions, "allowed_actions": [], "expected": expected}
        )
        answers = {}
        for key, q in questions.items():
            value = expected.get(key, next(iter(q.criteria)) if q.type == "choice" else 0)
            if isinstance(value, list):
                value = value[0]
            if q.type == "choice" and value not in q.criteria:
                value = next(iter(q.criteria))
            answers[key] = {"type": q.type, "value": value, "probabilities": None, "confidence": None}
        business.apply({"answers": answers})
    return items


class Benchmark:
    def __init__(self, config, adapters, gates, store):
        self.id, self.config = uuid4().hex, config
        self.adapters, self.gates, self.store = adapters, gates, store
        self.status, self.progress, self.results, self.error = "running", 0, {}, None
        self.cancelled = False
        self.current_run = None
        self.task = None
        self.metadata = hardware()
        self.created_at = datetime.now(UTC).isoformat()

    def view(self):
        return {
            "id": self.id,
            "kind": "benchmark",
            "status": self.status,
            "progress": self.progress,
            "config": self.config.model_dump(),
            "results": self.results,
            "error": self.error,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "quality_note": "Games: reference-action agreement, not an optimal-policy accuracy guarantee.",
        }

    async def execute(self):
        try:
            if self.config.mode == "episodes":
                await self._episodes()
            else:
                await self._corpus()
            self.status = "cancelled" if self.cancelled else "completed"
        except Exception as exc:
            self.status, self.error = "failed", str(exc)
        finally:
            await self.store.save_setting("benchmark:" + self.id, self.view())

    async def _corpus(self):
        items = await asyncio.to_thread(corpus, self.config)
        total = len(self.config.providers) * len(items)
        for provider in self.config.providers:
            if self.cancelled:
                break
            adapter, gate = self.adapters[provider], self.gates[provider]
            values, rows, errors = [], [], []
            self.results[provider] = {
                "latency": percentiles([]),
                "quality": None,
                "errors": errors,
                "rows": rows,
            }
            async with gate:
                ready = await adapter.warmup()
                for i in range(self.config.warmup + len(items)):
                    if self.cancelled:
                        break
                    sample = items[(i - self.config.warmup) % len(items)]
                    req = DecisionRequest(
                        run_id=self.id,
                        episode_id="corpus",
                        state_seq=i,
                        schema_id=self.config.scenario + "/1",
                        state=sample["state"],
                        questions=sample["questions"],
                        allowed_actions=sample["allowed_actions"],
                        budget_ms=60000,
                        max_state_age_ms=60000,
                    )
                    start = time.perf_counter()
                    try:
                        result = await adapter.decide(req)
                        elapsed = (time.perf_counter() - start) * 1000
                        if i >= self.config.warmup:
                            values.append(elapsed)
                            rows.append(
                                {
                                    "id": f"sample-{i - self.config.warmup}",
                                    "state": sample["state"],
                                    "answers": {k: v.model_dump() for k, v in result.answers.items()},
                                    "expected": sample["expected"],
                                    "latency_ms": elapsed,
                                    "model": result.model,
                                    "usage": result.usage,
                                }
                            )
                    except Exception as exc:
                        if i < self.config.warmup:
                            raise
                        errors.append({"index": i - self.config.warmup, "error": str(exc)})
                    if i >= self.config.warmup:
                        self.progress += 1 / total
                        self.results[provider].update(
                            latency=percentiles(values),
                            quality=evaluate(rows),
                            warmup=ready,
                            deadline_miss_rate=sum(v > self.config.budget_ms for v in values) / len(values)
                            if values
                            else None,
                        )
                    await asyncio.sleep(0)

    async def _episodes(self):
        for provider in self.config.providers:
            result = {"episodes": [], "score": None}
            self.results[provider] = result
            for i in range(self.config.episodes):
                if self.cancelled:
                    return
                run = Run(
                    RunConfig(
                        scenario=self.config.scenario,
                        provider=provider,
                        seed=self.config.seed + i,
                        budget_ms=self.config.budget_ms,
                        max_state_age_ms=max(200, self.config.budget_ms),
                        max_seconds=self.config.episode_seconds,
                        options=self.config.options,
                        dataset=self.config.dataset,
                    ),
                    self.adapters[provider],
                    self.store,
                    self.gates[provider],
                )
                self.current_run = run
                await run.start()
                await run.task
                result["episodes"].append(run.summary())
                scores = [
                    x["metrics"]["score"] for x in result["episodes"] if x["metrics"]["score"] is not None
                ]
                result["score"] = percentiles(scores)
                self.progress += 1 / (len(self.config.providers) * self.config.episodes)
                self.current_run = None


def calibrate(rows, temperature):
    """Explicit exploratory transform; never overwrites raw results or claims held-out fitting."""
    adjusted = copy.deepcopy(rows)
    for row in adjusted:
        for answer in row.get("answers", {}).values():
            if answer.get("probabilities"):
                answer["probabilities"] = temperature_scale(answer["probabilities"], temperature)
                answer["confidence"] = None
            elif answer["type"] == "boolean_probability":
                p = float(answer["value"])
                answer["value"] = temperature_scale({"false": 1 - p, "true": p}, temperature)["true"]
    return evaluate(adjusted)
