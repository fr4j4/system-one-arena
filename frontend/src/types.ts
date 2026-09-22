export type Scenario = {
  id: string;
  name: string;
  category: string;
  description: string;
  kind: "game" | "business";
};
export type Provider = {
  id: string;
  description: string;
  configured: boolean;
  probabilities: boolean;
  internal_timings: boolean;
};
export type Answer = {
  type: string;
  value: string | number;
  probabilities: Record<string, number> | null;
  confidence: number | null;
};
export type Result = {
  model: string;
  answers: Record<string, Answer>;
  timings: Record<string, number | null>;
  raw: Record<string, unknown>;
  usage: Record<string, unknown>;
};
export type Event = {
  seq: number;
  kind: string;
  elapsed_ms: number;
  request_id?: string;
  result?: Result;
  late?: boolean;
  error?: string;
  reason?: string;
  [key: string]: any;
};
export type Snapshot = {
  state_seq: number;
  state: Record<string, any>;
  questions: Record<string, unknown>;
  allowed_actions: string[];
};
export type Stats = {
  count: number;
  p50: number | null;
  p95: number | null;
  p99: number | null;
  mean: number | null;
};
export type Quality = {
  count: number;
  accuracy: number | null;
  macro_f1: number | null;
  brier: number | null;
  ece: number | null;
  mae: number | null;
  confusion: Record<string, Record<string, Record<string, number>>>;
  calibration: {
    lower: number;
    count: number;
    probability: number | null;
    accuracy: number | null;
  }[];
};
export type Metrics = {
  counts: Record<string, number>;
  provider_ms: Stats;
  end_to_end_ms: Stats;
  state_age_ms: Stats;
  inference_ms: Stats;
  queue_ms: Stats;
  overhead_ms: Stats;
  paint_ms: Stats;
  decisions_per_second: number;
  quality: Quality | null;
  score: number | null;
};
export type RunConfig = {
  scenario: string;
  provider: string;
  mode: string;
  seed: number;
  decision_hz: number;
  budget_ms: number;
  max_state_age_ms: number;
  speed: number;
  representation: string;
  controller: string;
  max_seconds: number;
  options: Record<string, unknown>;
  dataset?: any[];
  graph?: Graph;
};
export type Run = {
  id: string;
  status: string;
  error: string | null;
  config: RunConfig;
  created_at: string;
  snapshot?: Snapshot;
  events?: Event[];
  metrics: Metrics;
  last_result?: Result;
  last_request?: Record<string, unknown>;
  rows?: any[];
  warmup?: Record<string, unknown>;
};
export type GraphNode = {
  id: string;
  kind: "question" | "condition" | "output";
  question?: any;
  next?: string;
  source?: string;
  operator?: string;
  value?: string | number;
  yes?: string;
  no?: string;
  label?: string;
  position?: { x: number; y: number };
};
export type Graph = { start: string; nodes: GraphNode[] };
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch("/api" + path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!r.ok) {
    const body = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : JSON.stringify(body.detail),
    );
  }
  return r.json();
}
export const post = <T>(path: string, data: unknown) =>
  api<T>(path, { method: "POST", body: JSON.stringify(data) });
export const ms = (n: number | null | undefined) =>
  n == null ? "—" : n < 10 ? n.toFixed(1) : Math.round(n).toString();
export const pct = (n: number | null | undefined) =>
  n == null ? "—" : (n * 100).toFixed(1) + "%";
export const terminal = (s: string) =>
  ["completed", "failed", "stopped", "cancelled", "interrupted"].includes(s);
export function download(name: string, value: unknown) {
  const blob = new Blob(
    [typeof value === "string" ? value : JSON.stringify(value, null, 2)],
    { type: "application/json" },
  );
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
