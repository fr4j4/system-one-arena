# Verification record — 2026-09-21

Implementation was verified on Linux x86_64, Intel i5-9400F, approximately 16 GB RAM, Python 3.11.15 and Node 26.8.1. No functioning CUDA driver was available. Browser runs used Chromium through Playwright.

## Automated checks

- **67 Python tests passed** (protocol, every scenario, metrics, DAGs, API, WebSocket, storage, temporal invariants and independent simulation process).
- **6 end-to-end browser tests passed**: desktop preview/live metrics/timeline; tic-tac-toe step mode; ticket processing/replay; graph templates/validation and datasets; paired benchmark; mobile overflow.
- TypeScript check and Vite production build passed. Workflow editor, history, datasets and benchmark views are separate lazy chunks; fonts are bundled locally.
- Ruff check and format check passed.
- Docker Compose config validation passed for `lite`, `cpu` and `gpu` profiles. Images were **not built or run** here: no Docker daemon/socket was available.
- Two dependency deprecation warnings remain in Starlette's TestClient (`httpx` and an AnyIO alias). Tests passed; these warnings are not runtime failures.

A regression test first reproduced starvation of metrics events by the continuous snapshot stream, then passed after heartbeat scheduling was made independent of traffic. Simulation tests also verify expired and wrong-episode results never apply, duplicate actions are rejected, and slow inference does not pause physics. Restart recovery marks unfinished persisted runs as interrupted.

## Real providers

### TypeSafe Jev

A user-supplied credential was loaded only from a local ignored `.env` (mode 0600). The official endpoint returned `jev-1.13.0`, valid typed answers, probability distributions and usage. A synthetic Spanish billing ticket completed through the full API → coordinator → adapter → application → persistence path.

For that **single three-question integration request**, the observed call took ~307 ms; acceptance-to-application ~307.5 ms. No internal server-inference duration is claimed. The key is not stored in fixtures, screenshots, response data, tracked files, image build context or CI.

### Laya

A separate temporary CPU environment loaded real `convaiinnovations/laya` / `multilingual` weights with `laya 0.3.4`, `torch 2.7.1+cpu` and `transformers 4.57.6`.

- A single-question billing smoke request completed at ~174 ms local SDK time (~172 ms synchronized forward pass).
- Initial states and schemas from **all fifteen scenarios** were accepted and evaluated by the real checkpoint with the default 1024/256 token budgets.
- A complete three-question ticket run through the resident worker and coordinator completed at ~604 ms provider-call time (~599 ms forward pass).
- All those runs used synthetic data. Per-scenario smoke latencies varied substantially with input size, question count and concurrent testing.

These are integration checks, **not** a statistically controlled Laya/Jev speed or quality comparison. No accuracy claim should be inferred from one ticket. Run matched-state benchmarks on the target GPU machine for meaningful p50/p95/p99 and quality measurements. No CUDA inference, VRAM behavior or GPU image startup was verified here.

## Practical limits

- The shipped fixtures are a small synthetic starter set. Import representative held-out data for real accuracy/calibration work.
- Temperature adjustment is exploratory; automatic held-out temperature fitting is not implemented.
- Games are simplified structured-state simulations, not wrappers for commercial games.
- Generic chat-completions adapter is contract-validated but no third-party generic endpoint was configured for a live integration test.
- History/replay reproduces recorded state snapshots, not an identical fresh provider response. Model APIs can change versions; actual result model IDs and all effective settings are stored.
- Local Laya input truncation and CUDA-to-CPU fallback are explicitly detected/rejected. Larger state/option experiments may require documented budget overrides.

## 2026-09-22: remote-provider game deadlines

User traces showed 218 completed Jev Tetris responses and zero applied actions: every response exceeded the original 100 ms budget (observed p50 284 ms). Raised the explicit UI and protocol defaults to a 1000 ms budget and 1500 ms maximum state age; custom stricter limits still expire normally. The live panel now explains deadline/age discards and displays the configured limits alongside observed p95.

A regression test with 300 ms provider latency failed before the change and passes for Snake and Tetris afterward. All 68 backend tests pass. Real Jev smoke runs applied 5 Snake actions and 11 Tetris actions, with observed p50 around 302/317 ms respectively. These checks establish action delivery, not game-playing quality.
