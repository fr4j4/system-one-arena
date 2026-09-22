export type Slot = {
  controller: "model" | "human" | "baseline";
  fighter_id: string;
  model_profile_id: string;
};
export type Config = {
  players: Slot[];
  arena_id: string;
  mode: "duel" | "training";
  preset: string;
  best_of: 1 | 3 | 5;
  round_seconds: number;
  decision_hz: number;
  budget_ms: number;
  max_age_ms: number;
  pace: "native" | "equal_windows";
  seed: number;
  max_seconds: number;
};
export type Profile = {
  id: string;
  name: string;
  provider: string;
  model: string;
  configured: boolean;
  ai: boolean;
};
export type Character = {
  id: string;
  name: string;
  title: string;
  element: string;
  color: string;
  role: string;
  description: string;
  ultimate: string;
  finisher: string;
};
export type Catalog = {
  fighters: Character[];
  arenas: { id: string; name: string; subtitle: string; color: string }[];
  actions: Record<string, string>;
  moves: Record<string, any>;
  routes: Record<string, any>;
  signatures: Record<string, any>;
  presets: Record<string, string>;
  rules_version: string;
};
export type Frame = {
  tick: number;
  epoch: number;
  round: number;
  phase: string;
  phase_left: number;
  timer: number;
  best_of: number;
  wins: number[];
  rounds: any[];
  winner: string | null;
  done: boolean;
  fighters: any[];
  projectiles: any[];
  events: any[];
  clash: any;
  cinematic: any;
  arena: string;
  paused?: boolean;
  preview?: boolean;
};
export type Player = Slot & {
  pending: boolean;
  counts: Record<string, number>;
  latency: { p50: number | null; p95: number | null; count: number };
  last_request: any;
  last_result: any;
  error: string | null;
  actual_model: string | null;
};
export type Match = {
  id: string;
  status: string;
  error: string | null;
  config: Config;
  players: Player[];
  state: Frame | null;
  created_at: string;
  active_seconds: number;
};
export type Settings = {
  quality: "high" | "medium" | "low";
  reducedMotion: boolean;
  reducedFlash: boolean;
  shake: boolean;
  master: number;
  music: number;
  effects: number;
  bindings: Record<string, string>;
  gamepad: Record<string, string>;
};
export const DEFAULT_GAMEPAD: Record<string, string> = {
  0: "jump",
  1: "signature",
  2: "light",
  3: "heavy",
  4: "dash_forward",
  5: "beam",
  6: "guard_high",
  7: "charge",
  8: "break",
  9: "pause",
  10: "ultimate",
  11: "combo_power",
  12: "jump",
  13: "crouch",
  14: "back",
  15: "forward",
};
export const DEFAULT_KEYS: Record<string, string> = {
  KeyA: "back",
  KeyD: "forward",
  KeyS: "crouch",
  Space: "jump",
  KeyJ: "light",
  KeyK: "heavy",
  KeyL: "guard_high",
  KeyU: "bolt",
  KeyI: "beam",
  KeyO: "signature",
  KeyH: "charge",
  KeyP: "ultimate",
  ShiftLeft: "dash_forward",
  KeyF: "evade",
  KeyG: "throw",
  KeyN: "low",
  KeyM: "overhead",
  KeyB: "launcher",
  Digit1: "combo_pressure",
  Digit2: "combo_air",
  Digit3: "combo_power",
  Digit4: "combo_chase",
  KeyR: "break",
};
export const DEFAULT_CONFIG: Config = {
  players: [
    {
      controller: "baseline",
      fighter_id: "ember",
      model_profile_id: "reference",
    },
    {
      controller: "baseline",
      fighter_id: "flux",
      model_profile_id: "aggressive",
    },
  ],
  arena_id: "sanctuary",
  mode: "duel",
  preset: "neutral",
  best_of: 3,
  round_seconds: 90,
  decision_hz: 3,
  budget_ms: 800,
  max_age_ms: 1000,
  pace: "native",
  seed: 42,
  max_seconds: 900,
};
export async function api<T = any>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(
    "/api/v2" + path,
    body === undefined
      ? undefined
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const data = await r.json();
  if (!r.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  return data;
}
