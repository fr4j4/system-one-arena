# System One Arena

Accepted scope: six structured-state games (tic-tac-toe, Snake, Pong, Tetris, fighting, Space Invaders), eight business scenarios, editable decision DAGs, live telemetry, paired evaluations, replay, Laya local and Jev remote. Spanish UI; Spanish/English fixtures. No perception, game automation or real external business actions.

Architecture: React/Vite console; FastAPI coordinator; isolated simulation processes and resident Laya process; async remote adapters; SQLite WAL persistence. Versioned typed decision protocol, explicit deadlines, at most one physical call plus newest pending state per agent. Raw provider confidence is not selected-option probability. Missing telemetry is null. No synthetic reasoning or token streaming.

Design: a flight-recorder-like instrument console. Ink #111c2b, slate #243348, paper #edf2f6, blue #377dff, cyan #43d8cf, amber #f5ba63. Condensed system display typography, readable system body, monospace telemetry. Signature: the shared decision timeline joins observable request stages to the scene. UI remains readable without external fonts.

Delivery: protocol/adapters → runner and storage → six games → business scenarios/DAG → console → benchmarking/replay → portable deployment and verification. No sub-agents are required.


## Revised experience model (2026-09-22)

Scenario metadata declares `turns`, `realtime` or `batch`. Run policy derives from scenario, never the selected provider. Turn-based worlds change their state revision only on moves. Turns and datasets use a 30-second technical timeout and ignore continuous-world age limits; only continuous games expose optional scheduling limits. Batch runs finish on sample exhaustion rather than game duration. Continuous evaluation fixes speed at 1×; play uses an explicit fixed selected speed.

Dataset sampling is seeded and without replacement, optionally balanced by category and filtered by difficulty. All nine business scenarios expose 240 versioned Spanish synthetic compositions each, transparently grouped into 24 families and 10 contexts. Eight domain corpora are distinct; support workflows reuse ticket inputs with workflow-specific IDs. Labels/rationales never enter model input. CSV/JSONL import, full processed result tables, history and paired case alignment all use stable IDs. API and UI cap sample size to actual availability. Technical failures are retained separately from quality denominators.

## Fighting: shared simulation, independent players

`FightingWorld` owns combat and rounds; `Simulation` advances it at 60 Hz on an XY plane. `BattleRun` schedules one loop per slot, routes perspective-specific `fighting/2` questions through existing adapters, and tags every decision with player/round. Provider gates remain shared. No inference runs on the browser or blocks physics. The common stop event halts the world before pending calls finish.

`FightingArena.tsx` lazily loads Three.js. Its procedural Ember/Flux rigs animate authoritative state, with a responsive side camera that frames both fighters. Renderer, geometry, materials, shadows, resize observer and animation loop are disposed on unmount. History uses the same renderer. The UI exposes provider slots, best-of and round length; low-level deadline/frequency settings remain advanced, and A/B independent worlds are hidden for this shared battle.
