"""One background writer batches durable events; the inference path only enqueues."""

import asyncio
import json
import sqlite3
from pathlib import Path


class Store:
    def __init__(self, root):
        Path(root).mkdir(parents=True, exist_ok=True)
        self.path = Path(root) / "arena.sqlite3"
        with sqlite3.connect(self.path) as db:
            db.executescript("""PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events(run_id TEXT, seq INTEGER, data TEXT NOT NULL,
                    PRIMARY KEY(run_id, seq));
                CREATE TABLE IF NOT EXISTS settings(id TEXT PRIMARY KEY, data TEXT NOT NULL);""")
            for key, raw in db.execute("SELECT id, data FROM runs").fetchall():
                data = json.loads(raw)
                if data.get("status") in ("preparing", "running", "paused"):
                    data.update(status="interrupted", error="Backend restarted before the run finished")
                    db.execute("UPDATE runs SET data=? WHERE id=?", (json.dumps(data), key))
        self.queue = asyncio.Queue(maxsize=20000)
        self.task = None

    def start(self):
        self.task = asyncio.create_task(self._writer())

    async def _writer(self):
        while True:
            batch = [await self.queue.get()]
            while len(batch) < 256 and not self.queue.empty():
                batch.append(self.queue.get_nowait())
            try:
                await asyncio.to_thread(self._write, batch)
            finally:
                for _ in batch:
                    self.queue.task_done()

    def _write(self, batch):
        with sqlite3.connect(self.path) as db:
            for kind, key, seq, data in batch:
                if kind == "event":
                    db.execute("INSERT INTO events VALUES(?,?,?)", (key, seq, data))
                else:
                    table = "runs" if kind == "run" else "settings"
                    db.execute(f"INSERT OR REPLACE INTO {table} VALUES(?,?)", (key, data))

    async def save_run(self, data):
        self._check_writer()
        await self.queue.put(("run", data["id"], 0, json.dumps(data, ensure_ascii=False)))

    async def event(self, run_id, event):
        self._check_writer()
        await self.queue.put(("event", run_id, event["seq"], json.dumps(event, ensure_ascii=False)))

    async def save_setting(self, key, data):
        self._check_writer()
        await self.queue.put(("setting", key, 0, json.dumps(data, ensure_ascii=False)))

    async def flush(self):
        self._check_writer()
        joined = asyncio.create_task(self.queue.join())
        try:
            await asyncio.wait([joined, self.task], return_when=asyncio.FIRST_COMPLETED)
            self._check_writer()
        finally:
            joined.cancel()
            await asyncio.gather(joined, return_exceptions=True)

    def _check_writer(self):
        if self.task.done():
            self.task.result()

    def _read(self, query, args=()):
        with sqlite3.connect(self.path) as db:
            return [json.loads(r[0]) for r in db.execute(query, args)]

    async def runs(self):
        await self.flush()
        return await asyncio.to_thread(self._read, "SELECT data FROM runs ORDER BY rowid DESC LIMIT 200")

    async def run(self, key):
        await self.flush()
        rows = await asyncio.to_thread(self._read, "SELECT data FROM runs WHERE id=?", (key,))
        return rows[0] if rows else None

    async def events(self, key, after=0, limit=10000):
        await self.flush()
        return await asyncio.to_thread(
            self._read,
            "SELECT data FROM events WHERE run_id=? AND seq>? ORDER BY seq LIMIT ?",
            (key, after, limit),
        )

    async def settings(self):
        await self.flush()
        return await asyncio.to_thread(self._read, "SELECT data FROM settings ORDER BY id")

    async def close(self):
        await self.flush()
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)
