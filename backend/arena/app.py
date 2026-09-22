from __future__ import annotations

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field

from arena.adapters import make_adapters
from arena.battle import BattleRun
from arena.benchmark import Benchmark, BenchmarkConfig, calibrate
from arena.metrics import evaluate, hardware
from arena.protocol import DecisionRequest, RunConfig, StrictModel
from arena.runtime import Run
from arena.scenarios import SCENARIOS
from arena.scenarios.business import default_graph, fixtures, validate_dataset, validate_graph
from arena.storage import Store

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


@asynccontextmanager
async def lifespan(app):
    app.state.store = Store(os.getenv("ARENA_DATA_DIR", "data"))
    app.state.store.start()
    app.state.adapters = make_adapters()
    app.state.gates = {k: asyncio.Semaphore(1 if k == "laya" else 4) for k in app.state.adapters}
    app.state.runs = {}
    app.state.benchmarks = {}
    yield
    for benchmark in app.state.benchmarks.values():
        benchmark.cancelled = True
        if benchmark.current_run:
            benchmark.current_run.status = "stopped"
    await asyncio.gather(*(run.stop() for run in app.state.runs.values()), return_exceptions=True)
    await asyncio.gather(*(b.task for b in app.state.benchmarks.values() if b.task), return_exceptions=True)
    await asyncio.gather(*(adapter.close() for adapter in app.state.adapters.values()))
    await app.state.store.close()


app = FastAPI(title="System One Arena", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def local_guard(request: Request, call_next):
    # No browser can use ambient localhost access cross-origin. No public CORS wildcard.
    origin = request.headers.get("origin")
    if origin:
        from urllib.parse import urlparse

        if urlparse(origin).netloc != request.headers.get("host"):
            from fastapi.responses import JSONResponse

            return JSONResponse({"detail": "Cross-origin access is disabled"}, status_code=403)
    length = int(request.headers.get("content-length", "0"))
    if length > 10_000_000:
        from fastapi.responses import JSONResponse

        return JSONResponse({"detail": "Request exceeds 10 MB"}, status_code=413)
    return await call_next(request)


@app.get("/api/health")
async def health():
    return {"ok": True, "protocol_version": "1.0", "hardware": hardware()}


@app.get("/api/protocol")
async def protocol():
    return DecisionRequest.model_json_schema()


@app.get("/api/scenarios")
async def scenarios():
    return SCENARIOS


@app.get("/api/providers")
async def providers():
    descriptions = {
        "reference": "Heurística determinista · sin IA",
        "random": "Azar reproducible · sin IA",
        "simulated": "Heurística + 35 ms · sin IA",
        "laya": "Modelo local · CPU / CUDA",
        "jev": "TypeSafe API",
        "generic": "Chat completions · JSON",
    }
    return [
        {
            **a.capabilities(),
            "description": descriptions[key],
            "configured": key not in ("laya", "jev", "generic")
            or (
                os.getenv("LAYA_ENABLED", "false").lower() == "true"
                if key == "laya"
                else bool(os.getenv("TYPESAFE_API_KEY"))
                if key == "jev"
                else bool(os.getenv("GENERIC_BASE_URL") and os.getenv("GENERIC_MODEL"))
            ),
        }
        for key, a in app.state.adapters.items()
    ]


@app.get("/api/preview/{scenario}")
async def preview(scenario: str):
    from arena.scenarios.business import Business
    from arena.scenarios.games import CATALOG, Game

    if scenario not in {s["id"] for s in SCENARIOS}:
        raise HTTPException(404, "Escenario desconocido")
    if scenario in {s[0] for s in CATALOG}:
        return {"state": Game(scenario).observe()}
    return {"state": Business(scenario).observe()}


def validate_config(config):
    if config.scenario not in {s["id"] for s in SCENARIOS}:
        raise HTTPException(422, "Escenario desconocido")
    provider_ids = getattr(config, "providers", [getattr(config, "provider", "")])
    if config.scenario == "fighting" and hasattr(config, "player2_provider"):
        provider_ids = [*provider_ids, config.player2_provider]
    if any(p not in app.state.adapters for p in provider_ids):
        raise HTTPException(422, "Proveedor desconocido")
    try:
        if config.dataset is not None:
            validate_dataset(config.dataset)
        graph = getattr(config, "graph", None)
        if graph:
            validate_graph(graph)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/runs", status_code=201)
async def create_run(config: RunConfig):
    validate_config(config)
    if any(b.status == "running" for b in app.state.benchmarks.values()):
        raise HTTPException(409, "Espera o cancela el benchmark antes de iniciar una sesión interactiva")
    active = [r for r in app.state.runs.values() if r.status in ("preparing", "running", "paused")]
    if len(active) >= 4:
        raise HTTPException(409, "Máximo cuatro ejecuciones activas; detén una antes de iniciar otra")
    # Keep only a bounded working set. Completed runs remain in SQLite.
    if len(app.state.runs) >= 100:
        for key, old in list(app.state.runs.items()):
            if old.task.done() and not old.subscribers:
                del app.state.runs[key]
                break
    run = (
        BattleRun(config, app.state.adapters, app.state.store, app.state.gates)
        if config.scenario == "fighting"
        else Run(
            config, app.state.adapters[config.provider], app.state.store, app.state.gates[config.provider]
        )
    )
    app.state.runs[run.id] = run
    await run.start()
    return run.view()


@app.get("/api/runs")
async def runs():
    persisted = {r["id"]: r for r in await app.state.store.runs()}
    persisted.update({key: run.summary() for key, run in app.state.runs.items()})
    return sorted(persisted.values(), key=lambda r: r["created_at"], reverse=True)[:200]


@app.get("/api/runs/{key}")
async def run_view(key: str):
    if key in app.state.runs:
        return app.state.runs[key].view()
    result = await app.state.store.run(key)
    if not result:
        raise HTTPException(404, "Ejecución no encontrada")
    return result


class Control(StrictModel):
    command: str
    action: str | None = None


@app.post("/api/runs/{key}/control")
async def control(key: str, body: Control):
    run = app.state.runs.get(key)
    if not run or run.status not in ("running", "paused", "preparing"):
        raise HTTPException(409, "La ejecución no está activa")
    try:
        await run.control(body.command, body.action)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"ok": True}


@app.get("/api/runs/{key}/events")
async def events(key: str, after: int = 0, limit: int = 10000):
    if after < 0 or not 1 <= limit <= 10000:
        raise HTTPException(422, "Paginación inválida")
    return await app.state.store.events(key, after, limit)


@app.get("/api/runs/{key}/export")
async def export(key: str):
    run = await run_view(key)

    async def stream():
        yield json.dumps({"kind": "manifest", "version": "1.0", "run": run}, ensure_ascii=False) + "\n"
        after = 0
        while True:
            batch = await app.state.store.events(key, after, 1000)
            if not batch:
                break
            for event in batch:
                yield json.dumps(event, ensure_ascii=False) + "\n"
            after = batch[-1]["seq"]

    return StreamingResponse(
        stream(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="arena-{key}.jsonl"'},
    )


@app.websocket("/api/runs/{key}/live")
async def live(websocket: WebSocket, key: str):
    from urllib.parse import urlparse

    origin = websocket.headers.get("origin")
    if origin and urlparse(origin).netloc != websocket.headers.get("host"):
        await websocket.close(code=1008)
        return
    run = app.state.runs.get(key)
    if not run:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    subscriber = asyncio.Queue(maxsize=512)
    run.subscribers.add(subscriber)
    try:
        await websocket.send_json({"kind": "initial", "run": run.view()})

        async def sender():
            last_metrics = time.perf_counter()
            while True:
                try:
                    event = await asyncio.wait_for(subscriber.get(), 1)
                    await websocket.send_json(event)
                except TimeoutError:
                    pass
                if time.perf_counter() - last_metrics >= 1:
                    await websocket.send_json(
                        {
                            "kind": "metrics",
                            "metrics": run.metrics(),
                            "status": run.status,
                            **({"players": run.summary()["players"]} if isinstance(run, BattleRun) else {}),
                        }
                    )
                    last_metrics = time.perf_counter()

        async def receiver():
            while True:
                body = await websocket.receive_json()
                if body.get("kind") == "probe":
                    await websocket.send_json({"kind": "probe_ack", "nonce": body.get("nonce")})
                elif body.get("kind") == "paint":
                    value = body.get("duration_ms")
                    if isinstance(value, (int, float)) and 0 <= value <= 60000:
                        run.paints.append(value)

        tasks = [asyncio.create_task(sender()), asyncio.create_task(receiver())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    except (WebSocketDisconnect, RuntimeError, asyncio.CancelledError):
        pass
    finally:
        run.subscribers.discard(subscriber)


@app.get("/api/fixtures/{scenario}")
async def fixture_data(scenario: str):
    try:
        return fixtures(scenario)
    except KeyError as exc:
        raise HTTPException(404, "No hay dataset para este escenario") from exc


@app.get("/api/graphs/{template}")
async def graph(template: str):
    if template not in ("support", "email", "incident"):
        raise HTTPException(404, "Plantilla desconocida")
    return default_graph(template)


@app.post("/api/graphs/validate")
async def validate_graph_route(body: dict):
    try:
        return validate_graph(body)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc


class Setting(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    kind: str
    name: str
    value: dict | list


@app.post("/api/presets")
async def save_preset(body: Setting):
    try:
        if body.kind == "graph":
            validate_graph(body.value)
        elif body.kind == "dataset":
            validate_dataset(body.value)
        else:
            raise ValueError("kind debe ser graph o dataset")
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    await app.state.store.save_setting(body.id, body.model_dump())
    return body


@app.get("/api/presets")
async def presets():
    return [s for s in await app.state.store.settings() if s.get("kind") != "benchmark"]


@app.post("/api/benchmarks", status_code=201)
async def benchmark(config: BenchmarkConfig):
    validate_config(config)
    if config.mode not in ("corpus", "episodes"):
        raise HTTPException(422, "mode debe ser corpus o episodes")
    if any(b.status == "running" for b in app.state.benchmarks.values()):
        raise HTTPException(409, "Ya hay un benchmark en curso")
    if any(r.status in ("running", "paused", "preparing") for r in app.state.runs.values()):
        raise HTTPException(409, "Detén las ejecuciones interactivas antes del benchmark aislado")
    job = Benchmark(config, app.state.adapters, app.state.gates, app.state.store)
    app.state.benchmarks[job.id] = job
    job.task = asyncio.create_task(job.execute())
    return job.view()


@app.get("/api/benchmarks/{key}")
async def benchmark_view(key: str):
    job = app.state.benchmarks.get(key)
    if job:
        return job.view()
    for item in await app.state.store.settings():
        if item.get("kind") == "benchmark" and item["id"] == key:
            return item
    raise HTTPException(404, "Benchmark no encontrado")


@app.post("/api/benchmarks/{key}/cancel")
async def benchmark_cancel(key: str):
    job = app.state.benchmarks.get(key)
    if not job:
        raise HTTPException(404, "Benchmark no encontrado")
    job.cancelled = True
    if job.current_run:
        job.current_run.status = "stopped"
    return {"ok": True}


class Evaluation(StrictModel):
    rows: list[dict] = Field(max_length=10000)
    threshold: float = Field(default=0.5, ge=0, le=1)
    temperature: float = Field(default=1, ge=0.05, le=10)


@app.post("/api/evaluate")
async def evaluation(body: Evaluation):
    try:
        return {
            "raw": evaluate(body.rows, body.threshold),
            "temperature_preview": calibrate(body.rows, body.temperature),
            "note": "Exploratory only: temperature has not been fitted on a separate calibration split.",
        }
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc


frontend = Path(os.getenv("ARENA_FRONTEND_DIR", "frontend/dist"))
if frontend.is_dir():
    app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

    @app.get("/")
    async def index():
        return FileResponse(frontend / "index.html")
