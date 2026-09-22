import asyncio
import sqlite3

import pytest
from arena.storage import Store


async def test_restart_marks_unfinished_runs_interrupted(tmp_path):
    first = Store(tmp_path)
    first.start()
    await first.save_run({"id": "unfinished", "status": "running", "metrics": {}})
    await first.close()
    second = Store(tmp_path)
    second.start()
    assert (await second.run("unfinished"))["status"] == "interrupted"
    await second.close()


async def test_storage_failure_is_reported_not_hung(tmp_path):
    store = Store(tmp_path)

    def failure(batch):
        raise sqlite3.OperationalError("disk full")

    store._write = failure
    store.start()
    await store.save_run({"id": "x"})
    with pytest.raises(sqlite3.OperationalError, match="disk full"):
        await asyncio.wait_for(store.flush(), 0.5)
    await asyncio.gather(store.task, return_exceptions=True)
