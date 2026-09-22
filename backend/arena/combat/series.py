import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from .session import Match


class Series:
    def __init__(self, config, registry, store):
        self.id = uuid4().hex
        self.config = config
        self.registry = registry
        self.store = store
        self.status = "running"
        self.results = []
        self.current = None
        self.error = None
        self.task = None
        self.created_at = datetime.now(UTC).isoformat()

    def view(self):
        return dict(
            id=self.id,
            kind="series",
            created_at=self.created_at,
            status=self.status,
            config=self.config.model_dump(),
            results=self.results,
            current_id=self.current.id if self.current else None,
            error=self.error,
        )

    async def run(self):
        try:
            for pair in range(self.config.pairs):
                for mirror in (False, True):
                    if self.status != "running":
                        return
                    config = self.config.match.model_copy(deep=True)
                    config.seed += pair
                    if mirror:
                        config.players = list(reversed(config.players))
                    self.current = Match(config, self.registry, self.store)
                    await self.current.start()
                    while not self.current.task.done():
                        if self.current.status == "paused":
                            error = self.current.error or "Partida pausada"
                            await self.current.stop()
                            raise RuntimeError(error)
                        await asyncio.sleep(0.1)
                    await self.current.task
                    result = self.current.view()
                    result.update(pair=pair + 1, mirrored=mirror)
                    self.results.append(result)
                    await self.store.save_setting(self.id, self.view())
                    if self.current.status in ("failed", "paused"):
                        raise RuntimeError(self.current.error or "Partida interrumpida")
            if self.status == "running":
                self.status = "completed"
        except Exception as exc:
            self.status = "failed"
            self.error = str(exc)
        finally:
            self.current = None
            await self.store.save_setting(self.id, self.view())

    async def stop(self):
        self.status = "stopped"
        if self.current:
            await self.current.stop()
        if self.task:
            await self.task
