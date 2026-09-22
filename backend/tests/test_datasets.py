import asyncio

import pytest
from arena.adapters import ReferenceAdapter
from arena.protocol import RunConfig
from arena.runtime import Run
from arena.scenarios.business import fixtures, validate_dataset
from arena.scenarios.datasets import sample
from arena.storage import Store


@pytest.mark.parametrize("name", ["tickets", "email", "spam"])
def test_versioned_corpus_has_unique_cases_and_disclosed_families(name):
    rows = fixtures(name)
    assert len(rows) == 240
    assert len({r["id"] for r in rows}) == len(rows)
    assert len({r["state"]["text"] for r in rows}) == len(rows)
    assert len({r["metadata"]["family"] for r in rows}) == 24
    assert {r["metadata"]["difficulty"] for r in rows} == {"claro", "difícil", "ambiguo"}
    assert all(r["metadata"]["rationale"] and "expected" not in r["state"] for r in rows)


def test_sampling_reproducible_balanced_capped_and_without_replacement():
    rows = fixtures("tickets")
    left, manifest = sample(rows, 100, "balanced", 42)
    right, other = sample(rows, 100, "balanced", 42)
    assert left == right and manifest == other
    assert set(manifest["groups"].values()) == {25}
    assert len({r["id"] for r in left}) == 100
    assert sample(rows, 100, "random", 43)[0] != left
    assert len(sample(rows, 500)[0]) == 240
    selected, _ = sample(rows, None, difficulty="ambiguo")
    assert len(selected) == 24
    assert all(r["metadata"]["difficulty"] == "ambiguo" for r in selected)


def test_imports_have_unique_stable_ids():
    assert validate_dataset([{"state": {"text": "a"}}])[0]["id"] == "import-1"
    with pytest.raises(ValueError, match="único"):
        validate_dataset([{"id": "x", "state": {}}, {"id": "x", "state": {}}])


@pytest.mark.parametrize("scenario", ["tickets", "tic-tac-toe"])
async def test_non_realtime_ignores_world_deadline_and_state_age(tmp_path, scenario):
    store = Store(tmp_path)
    store.start()
    run = Run(
        RunConfig(
            scenario=scenario,
            sample_size=2,
            budget_ms=10,
            max_state_age_ms=10,
            request_timeout_ms=2000,
            max_seconds=5,
        ),
        ReferenceAdapter("simulated", 150),
        store,
        asyncio.Semaphore(1),
    )
    try:
        await run.start()
        await run.task
        assert run.status == "completed"
        assert run.counts["applied"] >= 2
        assert run.counts["expired"] == 0
        if scenario == "tickets":
            assert len(run.business.results) == 2
            assert all(r["latency_ms"] >= 150 for r in run.business.results)
            assert run.sample_manifest["selected"] == 2
    finally:
        await store.close()


async def test_batch_records_failure_then_advances_and_keeps_unlabeled_case(tmp_path):
    class FailingOnce(ReferenceAdapter):
        calls = 0

        async def decide(self, request):
            self.calls += 1
            if self.calls == 1:
                raise ValueError("synthetic provider failure")
            return await super().decide(request)

    store = Store(tmp_path)
    store.start()
    dataset = [{"id": str(i), "state": {"text": "Hola"}} for i in range(3)]
    run = Run(
        RunConfig(scenario="email", dataset=dataset, sample_size=None),
        FailingOnce(),
        store,
        asyncio.Semaphore(1),
    )
    try:
        await run.start()
        await run.task
        assert len(run.business.results) == 3
        assert run.business.results[0]["status"] == "error"
        assert run.business.results[1]["status"] == "completed"
        assert run.metrics()["quality"]["accuracy"] is None
        assert run.counts["accepted"] == 3
    finally:
        await store.close()


def test_run_policy_normalizes_mode_and_locks_evaluation_speed():
    config = RunConfig(scenario="snake", mode="step", speed=0.25, options={"experience": "evaluate"})
    run = Run(config, None, None, None)
    assert run.config.mode == "realtime" and run.config.speed == 1
    assert config.speed == 0.25  # caller's config remains intact
    batch = Run(RunConfig(scenario="tickets", controller="human", mode="step"), None, None, None)
    assert batch.config.mode == "realtime" and batch.config.controller == "model"


async def test_batch_timeout_creates_one_error_per_case_without_retries(tmp_path):
    store = Store(tmp_path)
    store.start()
    run = Run(
        RunConfig(scenario="tickets", sample_size=2, request_timeout_ms=10),
        ReferenceAdapter("simulated", 50),
        store,
        asyncio.Semaphore(1),
    )
    try:
        await run.start()
        await run.task
        assert run.status == "completed"
        assert len(run.business.results) == 2
        assert all(r["status"] == "error" for r in run.business.results)
        assert run.counts["accepted"] == 2
        assert run.counts["applied"] == 0
    finally:
        await store.close()
