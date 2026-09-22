"""Combat-only local application. Legacy endpoints live on the legacy branch."""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from arena.combat.content import catalog
from arena.combat.engine import World
from arena.combat.profiles import Registry
from arena.combat.protocol import Control, MatchConfig, SeriesConfig
from arena.combat.series import Series
from arena.combat.session import Match
from arena.metrics import hardware
from arena.storage import Store

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


@asynccontextmanager
async def lifespan(app):
    app.state.store = Store(os.getenv("COMBAT_DATA_DIR", str(ROOT / "data/combat-v2")))
    app.state.store.start()
    app.state.registry = Registry()
    app.state.matches = {}
    app.state.series = {}
    yield
    await asyncio.gather(*(s.stop() for s in app.state.series.values()), return_exceptions=True)
    await asyncio.gather(*(m.stop() for m in app.state.matches.values()), return_exceptions=True)
    await app.state.registry.close()
    await app.state.store.close()


app = FastAPI(title="System One — Eclipse Arena", version="2.0.0", lifespan=lifespan)


@app.middleware("http")
async def local_guard(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin and urlparse(origin).netloc != request.headers.get("host"):
        return JSONResponse(status_code=403, content={"detail": "Cross-origin access is disabled"})
    try:
        size = int(request.headers.get("content-length", "0"))
    except ValueError:
        return JSONResponse(status_code=400, content={"detail": "Invalid content length"})
    if size > 1_000_000:
        return JSONResponse(status_code=413, content={"detail": "Request too large"})
    return await call_next(request)


@app.get("/api/health")
@app.get("/api/v2/health")
async def health():
    return dict(ok=True, version="2.0.0", hardware=hardware())


@app.get("/api/v2/catalog")
async def get_catalog():
    return catalog()


@app.get("/api/v2/profiles")
async def profiles():
    return app.state.registry.public()


@app.post("/api/v2/preview")
async def preview(config: MatchConfig):
    return World(config.model_dump()).snapshot()


def find_match(key):
    match = app.state.matches.get(key)
    if not match:
        match = next(
            (s.current for s in app.state.series.values() if s.current and s.current.id == key), None
        )
    if not match:
        raise HTTPException(404, "Partida no activa o no encontrada")
    return match


def busy():
    return any(m.status in ("running", "paused", "preparing") for m in app.state.matches.values()) or any(
        s.status == "running" for s in app.state.series.values()
    )


@app.post("/api/v2/matches", status_code=201)
async def create_match(config: MatchConfig):
    if busy():
        raise HTTPException(409, "Detén la partida o serie activa antes de iniciar otra")
    try:
        app.state.registry.validate(config)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    match = Match(config, app.state.registry, app.state.store)
    app.state.matches[match.id] = match
    if len(app.state.matches) > 30:
        for key, old in list(app.state.matches.items()):
            if old.task and old.task.done() and not old.subscribers:
                del app.state.matches[key]
                break
    await match.start()
    return match.view()


@app.get("/api/v2/matches")
async def matches():
    data = await app.state.store.runs()
    live = {m.id: m.view() for m in app.state.matches.values()}
    return sorted(
        [live.pop(m["id"], m) for m in data] + list(live.values()),
        key=lambda m: m["created_at"],
        reverse=True,
    )


@app.get("/api/v2/matches/{key}")
async def match_view(key: str):
    try:
        return find_match(key).view()
    except HTTPException:
        saved = await app.state.store.run(key)
        if not saved:
            raise HTTPException(404, "Partida no encontrada") from None
        return saved


@app.post("/api/v2/matches/{key}/control")
async def control(key: str, body: Control):
    match = find_match(key)
    try:
        await match.control(body.command)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return match.view()


@app.get("/api/v2/matches/{key}/events")
async def events(key: str, after: int = 0, limit: int = 1000):
    return await app.state.store.events(key, max(0, after), max(1, min(5000, limit)))


@app.get("/api/v2/matches/{key}/export")
async def export(key: str):
    manifest = await match_view(key)

    async def stream():
        yield json.dumps(dict(kind="manifest", match=manifest), ensure_ascii=False) + "\n"
        after = 0
        while True:
            page = await app.state.store.events(key, after, 1000)
            if not page:
                break
            for event in page:
                yield json.dumps(event, ensure_ascii=False) + "\n"
            after = page[-1]["seq"]

    return StreamingResponse(
        stream(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="combat-{key}.jsonl"'},
    )


@app.websocket("/api/v2/matches/{key}/live")
async def live(ws: WebSocket, key: str):
    origin = ws.headers.get("origin")
    if origin and urlparse(origin).netloc != ws.headers.get("host"):
        await ws.close(code=1008)
        return
    try:
        match = find_match(key)
    except HTTPException:
        await ws.close(code=1008)
        return
    await ws.accept()
    queue = asyncio.Queue(256)
    match.subscribers.add(queue)
    controller = ws.query_params.get("role") == "controller"

    async def receive():
        while True:
            data = await ws.receive_json()
            if data.get("kind") == "input" and controller:
                try:
                    seq = data.get("seq")
                    player = data.get("player")
                    if type(seq) is not int or type(player) is not int:
                        raise ValueError("Entrada inválida")
                    match.human(player, str(data.get("action", "neutral")), seq, bool(data.get("release")))
                except (ValueError, KeyError):
                    await ws.send_json(dict(kind="input_error", error="Entrada o jugador no válido"))

    receiver = None
    try:
        await ws.send_json(dict(kind="initial", match=match.view()))
        receiver = asyncio.create_task(receive())
        while not receiver.done():
            try:
                event = await asyncio.wait_for(queue.get(), 0.5)
            except TimeoutError:
                continue
            await ws.send_json(event)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        match.subscribers.discard(queue)
        if receiver:
            receiver.cancel()
        if (
            controller
            and any(s.controller == "human" for s in match.config.players)
            and match.status == "running"
        ):
            await asyncio.shield(match.control("pause"))
        if receiver:
            await asyncio.gather(receiver, return_exceptions=True)


@app.post("/api/v2/series", status_code=201)
async def create_series(config: SeriesConfig):
    if busy():
        raise HTTPException(409, "Detén la partida o serie activa")
    try:
        app.state.registry.validate(config.match)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    series = Series(config, app.state.registry, app.state.store)
    app.state.series[series.id] = series
    series.task = asyncio.create_task(series.run())
    return series.view()


@app.get("/api/v2/series")
async def series_list():
    saved = {s["id"]: s for s in await app.state.store.settings() if s.get("kind") == "series"}
    for s in saved.values():
        if s["status"] == "running":
            s["status"] = "interrupted"
    saved.update({s.id: s.view() for s in app.state.series.values()})
    return sorted(saved.values(), key=lambda s: s["created_at"], reverse=True)


@app.post("/api/v2/series/{key}/stop")
async def stop_series(key: str):
    series = app.state.series.get(key)
    if not series:
        raise HTTPException(404, "Serie no encontrada")
    await series.stop()
    return series.view()


frontend = Path(os.getenv("ARENA_FRONTEND_DIR", str(ROOT / "frontend/dist")))
if frontend.exists():
    app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

    @app.get("/")
    async def index():
        return FileResponse(frontend / "index.html")
