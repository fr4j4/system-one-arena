# System One Arena

A local-first, observable decision laboratory for **Laya, TypeSafe Jev and other models**. Spanish UI. Structured-state games, classification, filters and editable decision trees — with deadlines, probabilities, live telemetry, reproducible experiments and replay.

![Arena interface](docs/screenshots/arena.png)

## Run it

Requirements: Git, Python 3.11–3.13, [uv](https://docs.astral.sh/uv/), Node.js 22+, or Docker Compose. Python 3.11 is the tested default.

```bash
git clone git@github.com:fr4j4/system-one-arena.git
cd system-one-arena
cp .env.example .env
chmod 600 .env
make setup
make build
make run
```

Open **http://127.0.0.1:8000**. The default simulator is a deterministic heuristic with 35 ms added delay; it is explicitly labelled **not AI**. Reference and random baselines work without credentials or weights.

Set `TYPESAFE_API_KEY` in `.env` to use Jev. Never put it in a `VITE_*` variable. `.env` is ignored by Git **and** Docker build context. Only `.env.example` is tracked. The app never returns keys to the browser. Restart the backend after changes.

Development: `make run` in one terminal, `make dev` in another; open http://localhost:5173. Vite proxies `/api` including WebSocket.

### Containers

Run exactly one profile at a time; all use the same local port and persistent volumes:

```bash
# Small image: baselines, Jev and generic providers, no torch/weights
docker compose --profile lite up --build -d

# Local Laya, CPU-only torch (no CUDA libraries)
docker compose --profile cpu up --build -d

# Local Laya, NVIDIA GPU
docker compose --profile gpu up --build -d
```

GPU requires a compatible NVIDIA driver and NVIDIA Container Toolkit. The locked torch build uses CUDA 12.6; validate host driver support. CPU works on supported Linux/macOS/Windows Python platforms; CUDA is not portable to arbitrary GPUs. Container CPU wheels are locked for Python 3.11. ARM/macOS users can use native installation when a CPU wheel is unavailable for their container architecture.

UI and API are served from one image. Compose binds only `127.0.0.1`. `ARENA_PORT` changes the port. `.env` is read at runtime, not copied into images. `arena-data` stores SQLite; `arena-models` caches Hugging Face weights. The first Laya run downloads weights and warms the model before timing decisions. Internet is unnecessary for subsequent local inference once weights are cached; Jev still needs network access.

### Native Laya CPU

Use a separate environment so ordinary `uv sync` does not replace the CPU wheel with the CUDA distribution:

```bash
uv venv .venv-cpu --python 3.11
uv pip sync --python .venv-cpu/bin/python --torch-backend cpu requirements-cpu.lock
uv pip install --python .venv-cpu/bin/python --no-deps .
LAYA_ENABLED=true LAYA_DEVICE=cpu .venv-cpu/bin/uvicorn arena.app:app --host 127.0.0.1 --port 8000
```

On Windows replace `.venv-cpu/bin/` with `.venv-cpu/Scripts/` and set environment variables using your shell. For native NVIDIA GPU, `uv sync --frozen --extra laya` installs the locked CUDA distribution, then set `LAYA_ENABLED=true` and `LAYA_DEVICE=cuda` in `.env`.

Laya defaults to `multilingual`. Available `LAYA_CHECKPOINT` values: `english`, `multilingual`, `typed-decisions`. One checkpoint resides in the worker; restart to change it. `LAYA_MODEL_PATH` can point to a local snapshot. `LAYA_CPU_THREADS` defaults to 4. The effective device is checked after each inference; a hidden SDK CPU fallback fails the run so GPU/CPU measurements do not get mixed.

Laya silently truncates some inputs by default. Arena **rejects** requests exceeding actual tokenizer budgets. For long boards or many options, increase `LAYA_MAX_LEN` and `LAYA_HEAD_MAX_LEN` within checkpoint capabilities (e.g. multilingual `2048`/`512`), or shorten the state/schema. These are experimental configuration changes; record them and compare consistently. Full snapshots remain inspectable. Long Snake bodies and Tetris placement mode can exceed default limits; rejection is an observed limit, not a successful decision.

![Live inspector](docs/screenshots/live.png)

## Included scenarios

| Games | Decision interface | Reference |
|---|---|---|
| Tic-tac-toe | Legal cell | Minimax; minimax opponent |
| Snake | Relative straight/left/right | BFS path/space heuristic |
| Pong | Up/down/neutral | Ball-following heuristic |
| Tetris | Movement or final placement | Height/holes/lines heuristic |
| Fighting 2D | Approach/retreat/attack/block/neutral | Range/cooldown rule |
| Space Invaders | Movement + fire | Target tracking/evasion |

All are original simplified deterministic simulations. No ROMs, screenshots, vision stack or external game control. States are observable facts, not hidden opponent intentions. Each supports human controls, seed, speed, model selection, real-time and step modes.

Business scenarios: tickets, email, spam/phishing, moderation, event filters, hierarchical classification (tree/flat), incident prioritization and agent routing. A ninth scenario executes editable decision DAGs, with support/email/incident templates. Actions remain simulated.

Synthetic Spanish/English fixtures can be inspected in Datasets, edited as JSONL, imported and saved. `state` goes to the model; `expected` stays in the evaluator. Multiple acceptable labels are supported. Fixtures are intentionally small smoke-test data, not production benchmarks.

## Live experiments

- **Real time:** the world does not wait. Initial decision frequency 10 Hz, budget 100 ms, maximum state age 200 ms. Slower providers will visibly miss deadlines. Increase those values intentionally or slow the world; every setting is recorded.
- **Step mode:** click “Una decisión” to request one result and advance the world. Still enforces the selected budget.
- **A/B:** choose a second provider in advanced options. Identical seed, independent trajectories; this is not a same-state accuracy comparison.
- **Inspector:** exact input/schema, final probabilities, provider confidence, raw response, event timeline and measured durations. No simulated reasoning, internal attention maps or fake token streaming.
- **Replay:** recorded snapshots/actions; no new model calls. Export full runs as JSONL.

Separate measurements: provider p50/p95/p99, queue, synchronized local inference when available, acceptance-to-application, state age, deadline failures, throughput, and a browser paint/round-trip probe. A remote call's duration includes network. Missing internal timings remain null.

## Benchmarks

“Experimentos” offers:

1. **Same states:** fixed corpus sent to providers sequentially, with 20 warmup calls and 500 measured decisions by default. Cache disabled. Game agreement compares against a named heuristic, not an optimal ground truth. Hierarchical corpus paths use the reference labels; evaluate independent episodes to measure compounding errors.
2. **Independent episodes:** 30 matched seeds by default, 30 seconds each, preserving wall-clock deadlines. Reports score and per-run traces.

Calls use real configured services and can incur API usage. Select counts before starting. Cancel stops after the currently executing physical call. Interactive runs and benchmarks are mutually exclusive so comparison is not accidentally contaminated by local contention.

Metrics: accuracy, macro-F1, per-question confusion matrices, ordinal MAE, Brier and ECE when labels/distributions exist. Ambiguous labels contribute to set accuracy, not single-label calibration. Brier is averaged across questions; compare identical task mixes. The temperature control is an **exploratory transform**, not automatic calibration fitted on held-out data.

## Extend

- Provider: implement `Adapter.capabilities`, `warmup`, `decide`, `close` in `backend/arena/adapters.py`; register it and add contract tests. UI/scenarios consume neutral `DecisionResult` only.
- Generic provider: set `GENERIC_BASE_URL` (ending in `/v1`), `GENERIC_MODEL`, `GENERIC_API_KEY` for a chat-completions server supporting JSON-object output. Its self-reported probabilities are not trusted; they stay absent.
- Scenario: implement deterministic reset/observation/legal actions/step/snapshot and a typed question set. Add catalogue entry, Canvas renderer and seed/replay tests.
- Decision graphs: question → next; condition references an earlier answer; terminal output is a label. Cycles, missing targets, unreachable nodes and forward dependencies are rejected.

Architecture and contracts: [design](docs/design.md), [protocol](docs/protocol.md). FastAPI publishes `/docs` and `/api/protocol`.

## Verification

```bash
make setup
make test
make lint
make build
cd frontend
npx playwright install chromium
npm run test:e2e
```

Tests cover all scenarios, malformed provider output, confidence semantics, timing, duplicate/expired/wrong-episode actions, process isolation, DAG validation, paired evaluation, WebSocket and persistence. Browser tests cover live UI, step controls, datasets, graph editing, replay, benchmarks and mobile overflow. CI does not need API keys or download model weights.

Real provider smoke tests are separate from automated baselines. See [verification notes](docs/verification.md) for hardware and limitations of this implementation run. GPU performance must be measured on your deployment machine; published model-card latency is not a guarantee.

## Research references

- [Laya model card](https://huggingface.co/convaiinnovations/laya): checkpoints, architecture, limits and calibration caveats.
- [Laya implementation](https://github.com/NandhaKishorM/laya): tokenizer budgets, forward pass, device fallback.
- [TypeSafe quickstart](https://docs.typesafe.ai/introduction/quickstart): official endpoint and typed questions.
- [TypeSafe confidence](https://docs.typesafe.ai/confidence): confidence is distinct from selected-option probability.
- [Gymnasium environment API](https://gymnasium.farama.org/api/env/): reset/step/observation/action separation.

Single-user POC, not a multi-tenant service. For remote access, use a tunnel or authenticated TLS reverse proxy. Dataset exports contain the supplied inputs; keep sensitive experiments local.
