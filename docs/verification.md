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

## 2026-09-22: three scenario experiences and dataset results

- 80 Python tests pass, including scenario-derived execution policy, slow turn/batch calls that must not inherit world deadlines, timeout/error rows that advance exactly once, normalization of evaluation speed, unique sample IDs, balanced/reproducible sampling, and corpus-family provenance.
- Tickets, email and spam each contain 240 synthetic contextual compositions (24 families × 10 contexts). These are disclosed synthetic variants, not independent production observations. Other business scenarios retain starter datasets and accept imports through the same table/sampling workflow.
- Tables retain all processed rows (25 per page), per-question labels/accuracy, technical errors, latency, reference alternatives and case metadata. A/B matches by stable source ID. Missing labels produce no accuracy claim.
- CSV import supports quoted/multiline fields, JSON state/expected cells and expected.* columns. Request revision guards prevent late fixture loads from replacing imported or edited data.
- Production TypeScript/Vite build, Ruff lint and formatting pass. The light results table was visually inspected against the existing Arena design.
- All 9 browser tests pass: original game/step/history/graph/benchmark/mobile paths plus scenario-specific controls, A/B 100-case alignment and pagination, and CSV import with unlabeled-case filtering.
- Isolated real Jev verification completed five tickets, five emails and five spam cases with zero technical errors and recorded per-case latencies. Observed provider p50 was approximately 283/286/361 ms respectively; these are integration smoke checks, not controlled quality/speed benchmarks. A separate UI smoke run processed 14 tickets before being stopped externally.

## 2026-09-22: expand every remaining business corpus

Moderation, events, hierarchy, incidents and routing now each supply 240 versioned synthetic cases (24 disclosed families × 10 variants). Tickets/email/spam remain at 240; support workflows reuse the 240 ticket inputs with distinct IDs. No business scenario falls back to the former 3–4 examples; the obsolete starter registry was removed.

All nine corpora have unique IDs and texts within each corpus, rationale metadata and clear/difficult/ambiguous cases. Contract checks cover every choice option, boolean outcome, severity level and all hierarchical subcategories. Boundary cases distinguish anomaly from operator attention, security risk from service outage, reported quotations from direct abuse, and active from withdrawn requests. These remain synthetic contextual compositions, not independent production observations.

Validation: 88 backend tests pass; lint, formatting and production build pass. Browser regression checks all nine fixture endpoints and processes 100 moderation cases in an isolated server.

## 2026-09-22: shared Fighting 2.5D battle

- **100 Python tests passed**, including plane/bounds/jump physics, melee startup, guard, projectile travel/evasion, energy costs, round resets and bounded ties, player perspectives, independent pacing, shared-provider capacity, pause/resume, immediate world stop while both calls are pending, stale-round rejection, match completion, persistence and paired fighting corpus perspectives.
- **11 browser tests passed** against a separate server on port 8011. Fighting renders a real Three.js canvas, assigns reference/random to separate slots, applies decisions for both, selects the P2 input inspector, stops and fits a 390px viewport. The original game/dataset/workflow/benchmark tests also pass. Desktop/mobile screenshots were visually inspected; camera framing adapts to fighter separation. [Fighting screenshot](screenshots/fighting.png).
- Production TypeScript/Vite build, Ruff and Prettier checks pass. Three.js loads only with the Fighting view; its chunk is approximately 540 kB / 137 kB gzip. Vite reports its standard >500 kB chunk warning. The two existing TestClient dependency deprecation warnings remain.
- A seven-second **real Jev-vs-reference** integration run applied 13 P1 actions and 43 P2 actions with zero technical failures. Jev reported `jev-1.13.0`, observed provider p50 ~344 ms; final health was 31.5/92. This verifies routing and application, not comparative model quality. The key remained in ignored `.env`; no credential is included in artifacts. The new battle schema was not separately smoke-tested with real Laya weights.
- The full browser run exposed an intermittent template-switch issue in the workflow editor. React Flow measurement notifications were unnecessarily written back into the application graph; now only position changes are persisted. The final full browser suite passes.
- Characters and stage are procedural original assets with a limited animation set. WebGL2 is required for the 3D view; an explicit error leaves telemetry and stop controls available if rendering fails. The authoritative combat remains on the backend, in one XY plane. No commercial fighting-game assets or mechanics fidelity are claimed.
