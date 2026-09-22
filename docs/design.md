# System One Arena

Accepted scope: six structured-state games (tic-tac-toe, Snake, Pong, Tetris, fighting, Space Invaders), eight business scenarios, editable decision DAGs, live telemetry, paired evaluations, replay, Laya local and Jev remote. Spanish UI; Spanish/English fixtures. No perception, game automation or real external business actions.

Architecture: React/Vite console; FastAPI coordinator; isolated simulation processes and resident Laya process; async remote adapters; SQLite WAL persistence. Versioned typed decision protocol, explicit deadlines, at most one physical call plus newest pending state per agent. Raw provider confidence is not selected-option probability. Missing telemetry is null. No synthetic reasoning or token streaming.

Design: a flight-recorder-like instrument console. Ink #111c2b, slate #243348, paper #edf2f6, blue #377dff, cyan #43d8cf, amber #f5ba63. Condensed system display typography, readable system body, monospace telemetry. Signature: the shared decision timeline joins observable request stages to the scene. UI remains readable without external fonts.

Delivery: protocol/adapters → runner and storage → six games → business scenarios/DAG → console → benchmarking/replay → portable deployment and verification. No sub-agents are required.
