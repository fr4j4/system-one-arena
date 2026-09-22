import { useEffect, useRef, useState } from "react";
import {
  Activity,
  ChevronDown,
  Download,
  Pause,
  Play,
  SkipForward,
  Square,
} from "lucide-react";
import {
  api,
  ms,
  pct,
  post,
  terminal,
  type Event,
  type Run,
  type Result,
} from "./types";
import GameCanvas from "./GameCanvas";
import ResultsTable from "./ResultsTable";

export function Distribution({ result }: { result?: Result }) {
  if (!result)
    return (
      <div className="empty-small">
        Las probabilidades aparecerán cuando termine una decisión.
      </div>
    );
  return (
    <div className="distributions">
      {Object.entries(result.answers).map(([key, a]) => (
        <div className="distribution" key={key}>
          <div className="label-row">
            <strong>{key}</strong>
            <span className="answer-value">
              {typeof a.value === "number" ? a.value.toFixed(3) : a.value}
            </span>
          </div>
          {a.probabilities ? (
            Object.entries(a.probabilities).map(([option, p]) => (
              <div className="prob-row" key={option}>
                <span title={option}>{option}</span>
                <div className="prob-track">
                  <i style={{ width: p * 100 + "%" }} />
                </div>
                <b>{pct(p)}</b>
              </div>
            ))
          ) : a.type === "boolean_probability" ? (
            <div className="prob-row">
              <span>Verdadero</span>
              <div className="prob-track">
                <i style={{ width: Number(a.value) * 100 + "%" }} />
              </div>
              <b>{pct(Number(a.value))}</b>
            </div>
          ) : (
            <p className="muted">Distribución no disponible</p>
          )}
          {a.confidence != null ? (
            <small>Confianza del proveedor: {a.confidence.toFixed(3)}</small>
          ) : null}
        </div>
      ))}
    </div>
  );
}

export function Sparkline({
  events,
  budget,
}: {
  events: Event[];
  budget: number;
}) {
  const values = events
    .filter((e) => e.kind === "completed")
    .slice(-60)
    .map((e) => e.result?.timings.provider_ms ?? 0);
  const max = Math.max(budget * 1.4, ...values, 1),
    width = 440,
    height = 66;
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="sparkline"
      role="img"
      aria-label="Latencia de las últimas decisiones"
    >
      <line
        x1="0"
        x2={width}
        y1={height - (budget / max) * height}
        y2={height - (budget / max) * height}
        stroke="#c08a38"
        strokeDasharray="4 4"
      />
      {values.map((v, i) => (
        <rect
          key={i}
          x={(i * width) / 60}
          y={height - (v / max) * height}
          width={width / 60 - 2}
          height={Math.max(1, (v / max) * height)}
          rx="1"
          fill={v > budget ? "#ed8c65" : "#377dff"}
        />
      ))}
      {!values.length ? (
        <text x="12" y="36" fill="#708196" fontSize="12">
          Esperando mediciones reales…
        </text>
      ) : null}
    </svg>
  );
}

const labels: Record<string, string> = {
  preparing: "Preparando",
  running: "En vivo",
  paused: "En pausa",
  completed: "Completado",
  failed: "Error",
  stopped: "Detenido",
};
export default function RunPanel({
  initial,
  onError,
  onChange,
}: {
  initial: Run;
  onError: (s: string) => void;
  onChange?: () => void;
}) {
  const [run, setRun] = useState(initial),
    [events, setEvents] = useState<Event[]>(initial.events ?? []),
    [tab, setTab] = useState("probabilities"),
    [player, setPlayer] = useState("p1");
  const wsRef = useRef<WebSocket | null>(null),
    probes = useRef(new Map<string, number>());
  useEffect(() => {
    let disposed = false,
      retry: number | undefined,
      attempt = 0;
    const connect = () => {
      const ws = new WebSocket(
        `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/runs/${initial.id}/live`,
      );
      wsRef.current = ws;
      ws.onmessage = async ({ data }) => {
        if (disposed) return;
        const event = JSON.parse(data);
        if (event.kind === "initial") {
          setRun(event.run);
          setEvents(event.run.events ?? []);
          attempt = 0;
          return;
        }
        if (event.kind === "resync") {
          const fresh = await api<Run>("/runs/" + initial.id).catch(() => null);
          if (fresh && !disposed) {
            setRun(fresh);
            setEvents(fresh.events ?? []);
          }
          return;
        }
        if (event.kind === "metrics") {
          setRun((r) => ({
            ...r,
            metrics: event.metrics,
            status: event.status,
            players: event.players ?? r.players,
          }));
          return;
        }
        if (event.kind === "probe_ack") {
          const start = probes.current.get(event.nonce);
          if (start != null) {
            requestAnimationFrame(() => {
              if (ws.readyState === 1)
                ws.send(
                  JSON.stringify({
                    kind: "paint",
                    duration_ms: performance.now() - start,
                  }),
                );
            });
            probes.current.delete(event.nonce);
          }
          return;
        }
        if (event.kind === "snapshot") {
          setRun((r) => ({ ...r, snapshot: event }));
          return;
        }
        setEvents((old) => [...old, event].slice(-160));
        if (
          event.player_id &&
          (event.kind === "completed" || event.kind === "accepted")
        )
          setRun((r) => ({
            ...r,
            players: {
              ...r.players,
              [event.player_id]: {
                ...(r.players?.[event.player_id] ?? {
                  provider: event.provider,
                  counts: {},
                  provider_ms: r.metrics.provider_ms,
                }),
                ...(event.kind === "completed"
                  ? { last_result: event.result }
                  : { last_request: event.request }),
              },
            },
          }));
        if (event.kind === "completed")
          setRun((r) => ({ ...r, last_result: event.result }));
        if (event.kind === "accepted")
          setRun((r) => ({ ...r, last_request: event.request }));
        if (event.kind === "stopped")
          setRun((r) => ({ ...r, status: "stopped" }));
        if (event.kind === "ready")
          setRun((r) => ({
            ...r,
            status: "running",
            warmup: event.warmup,
            sample: event.sample,
          }));
        if (event.kind === "pause" || event.kind === "resume")
          setRun((r) => ({
            ...r,
            status: event.kind === "pause" ? "paused" : "running",
          }));
        if (
          (event.kind === "applied" || event.kind === "case_failed") &&
          event.row
        )
          setRun((r) => ({
            ...r,
            rows: [
              ...(r.rows ?? []).filter((x) => x.id !== event.row.id),
              event.row,
            ],
          }));
        if (event.kind === "failed")
          setRun((r) => ({ ...r, error: event.error }));
        if (event.kind === "finished") {
          setRun((r) => ({
            ...r,
            status: event.status,
            metrics: event.metrics,
            players: event.players ?? r.players,
          }));
          onChange?.();
        }
      };
      ws.onclose = () => {
        if (!disposed && attempt++ < 5)
          retry = window.setTimeout(connect, Math.min(10000, 1000 * attempt));
      };
    };
    connect();
    const heartbeat = window.setInterval(() => {
      const ws = wsRef.current;
      if (ws?.readyState === 1) {
        const nonce = String(performance.now());
        probes.current.set(nonce, performance.now());
        ws.send(JSON.stringify({ kind: "probe", nonce }));
      }
    }, 3000);
    return () => {
      disposed = true;
      clearTimeout(retry);
      clearInterval(heartbeat);
      wsRef.current?.close();
      probes.current.clear();
    };
  }, [initial.id]);
  const command = async (command: string, action?: string) => {
    try {
      await post("/runs/" + run.id + "/control", { command, action });
      if (command === "stop") setRun((r) => ({ ...r, status: "stopped" }));
    } catch (e) {
      onError(String(e));
    }
  };
  const m = run.metrics,
    active = !terminal(run.status),
    state = run.snapshot?.state;
  const execution =
    run.execution ??
    (run.config.scenario === "tic-tac-toe"
      ? "turns"
      : ["snake", "pong", "tetris", "fighting", "space-invaders"].includes(
            run.config.scenario,
          )
        ? "realtime"
        : "batch");
  const batch = execution === "batch";
  const fighting = run.config.scenario === "fighting";
  const inspectedResult = fighting
    ? run.players?.[player]?.last_result
    : run.last_result;
  const inspectedRequest = fighting
    ? run.players?.[player]?.last_request
    : run.last_request;
  return (
    <article className={"run-panel" + (fighting ? " fighting-run" : "")}>
      <header className="run-header">
        <div className="provider-name">
          <span className="model-avatar">
            {run.config.provider.slice(0, 1).toUpperCase()}
          </span>
          <div>
            <strong>
              {fighting
                ? "Batalla · Ember vs Flux"
                : run.config.provider === "simulated"
                  ? "Simulador"
                  : run.config.provider === "reference"
                    ? "Referencia"
                    : run.config.provider.toUpperCase()}
            </strong>
            <small>
              {batch
                ? "Dataset"
                : execution === "turns"
                  ? "Por turnos"
                  : "Tiempo real"}{" "}
              · semilla {run.config.seed}
            </small>
          </div>
        </div>
        <button
          className="pause-run-button"
          disabled={!active || run.status === "preparing"}
          onClick={() => command(run.status === "paused" ? "resume" : "pause")}
        >
          {run.status === "paused" ? <Play size={14} /> : <Pause size={14} />}
          {run.status === "paused" ? "Continuar" : "Pausar"}
        </button>
        <button
          className="stop-run-button"
          aria-label="Detener"
          disabled={!active}
          onClick={() => command("stop")}
        >
          <Square size={14} fill="currentColor" /> Detener
        </button>
        <span className={"status " + run.status}>
          <i />
          {labels[run.status] ?? run.status}
        </span>
      </header>
      {run.status === "preparing" ? (
        <div className="preparing-strip">
          <Activity size={14} /> Cargando y calentando el proveedor. Este tiempo
          no cuenta como inferencia.
        </div>
      ) : null}
      {execution === "realtime" && (m.counts.expired ?? 0) > 0 && (
        <div className="preparing-strip" role="status">
          {m.counts.expired} decisiones descartadas por plazo o antigüedad.
          Presupuesto: {run.config.budget_ms} ms; antigüedad máxima:{" "}
          {run.config.max_state_age_ms} ms. Latencia p95:{" "}
          {ms(m.provider_ms.p95)}. Si no hay movimientos, aumenta ambos límites
          antes de iniciar otra ejecución. La frecuencia solicitada no reduce la
          latencia del proveedor.
        </div>
      )}
      {fighting && (
        <div className="fighter-models">
          {["p1", "p2"].map((id, i) => {
            const slot = run.players?.[id];
            return (
              <button
                key={id}
                className={player === id ? "selected" : ""}
                onClick={() => setPlayer(id)}
                aria-pressed={player === id}
              >
                <b>
                  PLAYER {i + 1} ·{" "}
                  {(
                    slot?.provider ??
                    (i === 0
                      ? run.config.provider
                      : (run.config.player2_provider ?? "reference"))
                  ).toUpperCase()}
                </b>
                <span>
                  {slot?.counts.applied ?? 0} acciones aplicadas · p50{" "}
                  {ms(slot?.provider_ms.p50)} ms · {slot?.counts.expired ?? 0}{" "}
                  fuera de plazo
                </span>
                {slot?.error && <small>{slot.error}</small>}
              </button>
            );
          })}
        </div>
      )}
      {fighting && state?.rounds?.length > 0 && (
        <div className="round-results">
          {state?.rounds.map((r: any) => (
            <span key={r.round}>
              R{r.round}: {r.winner?.toUpperCase() ?? "Empate"} · {r.reason}
            </span>
          ))}
        </div>
      )}
      {batch && (
        <ResultsTable
          rows={run.rows ?? []}
          total={state?.total ?? run.sample?.selected}
          name={run.id}
        />
      )}
      <details className="execution-inspector" open={batch ? undefined : true}>
        <summary>
          {batch
            ? "Entrada actual e inspector del modelo"
            : "Arena e inspector del modelo"}
        </summary>
        <div className="live-body">
          <div className="scene-column">
            {state &&
            [
              "tic-tac-toe",
              "snake",
              "pong",
              "tetris",
              "fighting",
              "space-invaders",
            ].includes(state.scenario) ? (
              <GameCanvas state={state} />
            ) : (
              <div className="business-stage">
                <div className="document-count">
                  ENTRADA {(state?.index ?? 0) + 1} / {state?.total ?? "—"}
                </div>
                <blockquote>{state?.text ?? "Preparando entrada…"}</blockquote>
                {state?.node ? (
                  <div className="path">
                    <span>Nodo activo</span>
                    <b>{state.node}</b>
                    <small>{state.path?.join(" → ")}</small>
                  </div>
                ) : null}
              </div>
            )}
            <div className="transport">
              <div className="transport-buttons">
                {execution === "turns" && (
                  <button
                    title="Una decisión"
                    aria-label="Una decisión"
                    disabled={!active || run.config.mode !== "step"}
                    onClick={() => command("step")}
                  >
                    <SkipForward size={16} /> Siguiente turno
                  </button>
                )}
              </div>
              <span>
                Estado #{run.snapshot?.state_seq ?? 0} <b>·</b>{" "}
                {execution === "realtime"
                  ? `${run.config.speed}×`
                  : execution === "turns"
                    ? "Por turnos"
                    : "Por caso"}
              </span>
              <a
                className="icon-link"
                href={"/api/runs/" + run.id + "/export"}
                title="Exportar ejecución"
              >
                <Download size={15} />
              </a>
            </div>
            {run.config.controller === "human" ? (
              <div className="human-controls">
                {run.snapshot?.allowed_actions.map((a) => (
                  <button
                    key={a}
                    disabled={!active}
                    onClick={() => command("action", a)}
                  >
                    {a}
                  </button>
                ))}
              </div>
            ) : null}
            <div className="metric-grid">
              <Metric
                name="Llamada p50"
                value={ms(m.provider_ms.p50)}
                unit="ms"
              />
              <Metric
                name="Llamada p95"
                value={ms(m.provider_ms.p95)}
                unit="ms"
              />
              <Metric
                name="Hasta aplicar p95"
                value={ms(m.end_to_end_ms.p95)}
                unit="ms"
              />
              <Metric
                name="Fuera de plazo"
                value={String(m.counts.expired ?? 0)}
                unit=""
              />
            </div>
            <div className="latency-section">
              <div className="label-row">
                <span>LATENCIA POR DECISIÓN</span>
                <small>
                  <i className="budget-dot" /> presupuesto{" "}
                  {run.config.budget_ms} ms
                </small>
              </div>
              <Sparkline events={events} budget={run.config.budget_ms} />
            </div>
          </div>
          <aside className="live-inspector">
            <div className="inspector-tabs">
              {[
                ["probabilities", "Decisiones"],
                ["timeline", "Timeline"],
                ["input", "Entrada"],
                ["raw", "Respuesta"],
              ].map(([id, label]) => (
                <button
                  className={tab === id ? "selected" : ""}
                  key={id}
                  onClick={() => setTab(id)}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="inspector-body">
              {tab === "probabilities" ? (
                <Distribution result={inspectedResult} />
              ) : tab === "timeline" ? (
                <div className="timeline">
                  {events
                    .filter(
                      (e) =>
                        e.kind !== "snapshot" &&
                        (!fighting || !e.player_id || e.player_id === player),
                    )
                    .slice(-24)
                    .reverse()
                    .map((e) => (
                      <div className={"timeline-row " + e.kind} key={e.seq}>
                        <i />
                        <span>{e.kind}</span>
                        <code>{ms(e.elapsed_ms)} ms</code>
                        <small>
                          {e.reason ??
                            e.error ??
                            e.request_id?.slice(0, 7) ??
                            ""}
                        </small>
                      </div>
                    ))}
                </div>
              ) : (
                <pre>
                  {JSON.stringify(
                    tab === "input" ? inspectedRequest : inspectedResult?.raw,
                    null,
                    2,
                  ) ?? "Todavía no hay una decisión."}
                </pre>
              )}
            </div>
          </aside>
        </div>
      </details>
      {run.error ? <div className="inline-error">{run.error}</div> : null}
      <details className="detail-metrics">
        <summary>
          Telemetría adicional <ChevronDown size={13} />
        </summary>
        <dl>
          <dt>Inferencia local p50</dt>
          <dd>{ms(m.inference_ms.p50)} ms</dd>
          <dt>Cola p95</dt>
          <dd>{ms(m.queue_ms.p95)} ms</dd>
          <dt>Antigüedad al aplicar p95</dt>
          <dd>{ms(m.state_age_ms.p95)} ms</dd>
          <dt>Sobrecarga propia p95</dt>
          <dd>{ms(m.overhead_ms.p95)} ms</dd>
          <dt>Sonda UI → servidor → pintura p95</dt>
          <dd>{ms(m.paint_ms.p95)} ms</dd>
          <dt>Decisiones / segundo</dt>
          <dd>{m.decisions_per_second.toFixed(2)}</dd>
          <dt>Accuracy etiquetada</dt>
          <dd>{pct(m.quality?.accuracy)}</dd>
        </dl>
        <p>
          La llamada remota incluye red. La sonda de UI mide un intercambio
          independiente, no el tiempo interno del modelo.
        </p>
      </details>
    </article>
  );
}
export function Metric({
  name,
  value,
  unit,
}: {
  name: string;
  value: string;
  unit: string;
}) {
  return (
    <div className="metric">
      <span>{name}</span>
      <strong>
        {value}
        <small>{unit}</small>
      </strong>
    </div>
  );
}
