# Decision Protocol 1.0

The browser never calls a provider directly. REST creates a run, registering its scenario, schema, controls and provider once. The server owns simulation state. The browser receives events over a persistent WebSocket; keys remain in the backend environment.

## Contract

`GET /api/protocol` returns the executable JSON Schema for `DecisionRequest`.

```json
{
  "protocol_version": "1.0",
  "run_id": "...",
  "request_id": "...",
  "episode_id": "...",
  "state_seq": 42,
  "schema_id": "pong/1",
  "state": {"scenario":"pong","ball":[50,30],"velocity":[25,17],"paddle":30},
  "questions": {"action":{"type":"choice","instructions":"Move the paddle","criteria":{"up":"up","down":"down","neutral":"stay"}}},
  "allowed_actions": ["up","down","neutral"],
  "budget_ms": 100,
  "max_state_age_ms": 200
}
```

The illustrated state is abbreviated. Requests inside the backend include the complete observable state. Each provider receives identical semantic input; adapters translate types only. `schema_id` identifies a version; the request also captures the effective questions (legal game actions can change). No state deltas or generative explanations are required.

Primitive mapping: `choice → choice`, `ordinal → score` (0…N−1), `boolean_probability → noul` (0…1). Distributions must contain every option, finite values in [0,1], and sum to 1 within 0.02 (rounded provider outputs). Unknown answers are errors. Missing probabilities/confidence are null. Provider confidence is preserved, not recomputed as selected probability.

## Lifecycle and backpressure

`accepted → queued → started → completed → applied`, with `expired`, `rejected`, `failed`, and `finished`. `completed` may arrive after `expired`; it is recorded with `late=true` and never applied. One physical inference per run; the latest snapshot replaces intermediate observations while it is busy. No FIFO backlog of old game states. A provider semaphore bounds cross-run concurrency (Laya 1; HTTP 4). Queue waits count against the deadline. Only continuous games are sampled at a configured maximum frequency. Turns and batches dispatch when their prior decision has completed and any authoritative move is acknowledged.

A CPU/CUDA call cannot be forcibly interrupted safely. On a deadline, record expiration immediately but wait for the physical call to finish before issuing another. Pause/stop suppress application and new queries; stop signals the simulation process immediately. A request already sent cannot be undone. Every application revalidates episode, request uniqueness, deadline, observation age and current legal action. Tic-tac-toe additionally requires exact state sequence. Continuous games may apply a still-fresh action to a later state, and report its age.

World stepping is 60 Hz in an independent spawned process. States stream at up to 20 Hz. UI paints separately; continuous coordinates interpolate across snapshots. Step mode advances 12 physics ticks per requested decision. Physics speed and decision frequency are independent and stored in the manifest. Late-action behavior: Snake keeps heading; Pong/fighting/invaders go neutral; Tetris keeps gravity; tic-tac-toe waits.

A slow WebSocket reader receives `resync`; it must GET the run view and page `/events?after=...`. Telemetry is durable in SQLite. Run creation has a four-interactive-run limit. Benchmarks cannot overlap interactive runs. Simulation queues, subscribers and the persistence queue are bounded; sustained disk pressure backpressures coordination rather than losing durable events.

## Timing

Monotonic clocks measure local intervals. Simulation and coordinator processes share the same host clock; remote timestamps are never subtracted. `provider_ms` covers the adapter call including HTTP/network or local worker dispatch. Laya reports synchronized forward-hook `inference_ms` and SDK duration separately. End-to-end is server acceptance to authoritative application. Own overhead subtracts queue and provider durations from end-to-end. Browser probes measure an independent UI → server → next-paint exchange, **not** full model-to-paint latency. Cold loading and warmup are separate from measured decisions.

## API

- `GET /api/health`, `/scenarios`, `/providers`, `/protocol`, `/preview/{scenario}`
- `POST /api/runs` (`RunConfig`), `GET /api/runs`, `/runs/{id}`
- `POST /api/runs/{id}/control`: `pause`, `resume`, `stop`, `step`, `action`
- `WS /api/runs/{id}/live`: initial view, events, periodic metrics, probe acknowledgements
- `GET /api/runs/{id}/events?after=0&limit=10000`, `/export` (JSONL manifest + all events)
- `GET /api/fixtures/{scenario}`, `/graphs/{support|email|incident}`
- `POST /api/graphs/validate`, `GET/POST /api/presets`
- `POST /api/benchmarks`, `GET /api/benchmarks/{id}`, `POST /api/benchmarks/{id}/cancel`
- `POST /api/evaluate`: threshold evaluation and an explicit exploratory temperature transform

OpenAPI/interactive reference: `/docs`. Everything is single-user and intended for loopback access. No wildcard CORS. Bind publicly only behind an authenticated reverse proxy and TLS.


## Scenario policy and samples

`/scenarios` and run summaries expose `execution` (`turns`, `realtime`, `batch`). It is derived from scenario ID. Run construction normalizes non-turn modes to automatic processing and fixes continuous evaluation speed at 1×. `request_timeout_ms` (default 30000) controls turn/batch technical timeouts; their observation age is not a realtime deadline. `budget_ms`/`max_state_age_ms` apply to continuous worlds only.

`sample_size` (default 25, null = all), `sampling` (`random`/`balanced`), `difficulty` and `seed` select a finite dataset without replacement. Summaries include `sample`: requested/effective size, filtered availability, ordered IDs, categories and corpus versions. Built-in synthetic corpora disclose families and variants; imported cases require unique string IDs or receive sequential IDs. All sampled IDs persist in the manifest.

`applied` includes `row` only on completing a case; `case_failed` includes a failed row and advances to the next case. Rows retain status, error, input, expected labels, answers, accumulated provider-call latency, call count, metadata, path and terminal output. Failed rows do not contribute to quality metrics. Run views include all processed rows; the UI paginates 25 per page. `/events` remains the durable, paginated source after restart. Batch processing is not limited by game duration.
