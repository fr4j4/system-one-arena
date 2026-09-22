import { Suspense, lazy, useCallback, useEffect, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  Check,
  ChevronRight,
  CircleHelp,
  Database,
  FlaskConical,
  GitBranch,
  History as HistoryIcon,
  Layers3,
  Play,
  Plus,
  Settings2,
  SlidersHorizontal,
  Terminal,
  X,
  Zap,
} from "lucide-react";
import {
  api,
  post,
  type Graph,
  type Provider,
  type Run,
  type RunConfig,
  type Scenario,
} from "./types";
import RunPanel from "./RunPanel";
import GameCanvas from "./GameCanvas";
const WorkflowEditor = lazy(() => import("./WorkflowEditor"));
const Benchmarks = lazy(() => import("./Benchmarks"));
const Datasets = lazy(() => import("./Datasets"));
const History = lazy(() => import("./History"));
const NAV = [
  ["arena", "Arena", FlaskConical],
  ["benchmarks", "Experimentos", BarChart3],
  ["datasets", "Datasets", Database],
  ["workflow", "Árboles", GitBranch],
  ["history", "Historial", HistoryIcon],
  ["providers", "Proveedores", Layers3],
] as const;
const ICONS: Record<string, string> = {
  "tic-tac-toe": "╳",
  snake: "↱",
  pong: "Ⅱ",
  tetris: "▟",
  fighting: "⚔",
  "space-invaders": "⌁",
  tickets: "▤",
  email: "@",
  spam: "⊘",
  moderation: "◇",
  events: "∿",
  hierarchy: "⑂",
  incidents: "!",
  routing: "↗",
  workflow: "⋈",
};
export default function App() {
  const [page, setPage] = useState("arena"),
    [scenarios, setScenarios] = useState<Scenario[]>([]),
    [providers, setProviders] = useState<Provider[]>([]),
    [scenario, setScenario] = useState("snake"),
    [provider, setProvider] = useState("simulated"),
    [compare, setCompare] = useState(""),
    [runs, setRuns] = useState<Run[]>([]),
    [graph, setGraph] = useState<Graph>(),
    [datasets, setDatasets] = useState<Record<string, any[]>>({}),
    [preview, setPreview] = useState<any>(),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [advanced, setAdvanced] = useState(false),
    [category, setCategory] = useState("game"),
    [health, setHealth] = useState<any>();
  const [mode, setMode] = useState("realtime"),
    [seed, setSeed] = useState(42),
    [hz, setHz] = useState(10),
    [budget, setBudget] = useState(100),
    [age, setAge] = useState(200),
    [speed, setSpeed] = useState(1),
    [representation, setRepresentation] = useState("direct"),
    [controller, setController] = useState("model"),
    [seconds, setSeconds] = useState(180),
    [tetris, setTetris] = useState("movement"),
    [hierarchy, setHierarchy] = useState("tree");
  const onError = useCallback(
    (s: string) => setError(s.replace(/^Error: /, "")),
    [],
  );
  useEffect(() => {
    Promise.all([
      api<Scenario[]>("/scenarios"),
      api<Provider[]>("/providers"),
      api<Graph>("/graphs/support"),
      api("/health"),
    ])
      .then(([s, p, g, h]) => {
        setScenarios(s);
        setProviders(p);
        setGraph(g);
        setHealth(h);
      })
      .catch((e) =>
        onError("No se pudo conectar con el backend. " + String(e)),
      );
  }, [onError]);
  useEffect(() => {
    api("/preview/" + scenario)
      .then(setPreview)
      .catch(() => setPreview(undefined));
  }, [scenario]);
  const chosen = scenarios.find((s) => s.id === scenario);
  const start = async () => {
    setLoading(true);
    setError("");
    try {
      const active = await api<Run[]>("/runs");
      for (const r of active.filter((r) =>
        ["running", "paused", "preparing"].includes(r.status),
      )) {
        await post("/runs/" + r.id + "/control", { command: "stop" });
      }
      const config: RunConfig = {
        scenario,
        provider,
        mode,
        seed,
        decision_hz: hz,
        budget_ms: budget,
        max_state_age_ms: age,
        speed,
        representation,
        controller,
        max_seconds: seconds,
        options: { tetris_control: tetris, hierarchy_mode: hierarchy },
        ...(datasets[scenario] ? { dataset: datasets[scenario] } : {}),
        ...(scenario === "workflow" ? { graph } : {}),
      };
      const first = await post<Run>("/runs", config);
      setRuns([first]);
      if (compare) {
        const second = await post<Run>("/runs", {
          ...config,
          provider: compare,
        });
        setRuns([first, second]);
      }
    } catch (e) {
      onError(String(e));
    } finally {
      setLoading(false);
    }
  };
  const selectScenario = async (id: string) => {
    try {
      for (const run of runs) {
        const current = await api<Run>("/runs/" + run.id);
        if (["running", "paused", "preparing"].includes(current.status))
          await post("/runs/" + run.id + "/control", { command: "stop" });
      }
      setScenario(id);
      setRuns([]);
    } catch (error) {
      onError(String(error));
    }
  };
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setPage("arena");
          }}
        >
          <span className="brand-mark">
            <i />
            <i />
            <i />
          </span>
          <span>
            SYSTEM ONE<small>ARENA</small>
          </span>
        </a>
        <div className="workspace-label">
          DECISION LAB <span>v0.1</span>
        </div>
        <nav aria-label="Navegación principal">
          {NAV.map(([id, label, Icon]) => (
            <button
              key={id}
              className={page === id ? "active" : ""}
              onClick={() => setPage(id)}
            >
              <Icon size={18} />
              <span>{label}</span>
              {page === id ? <ChevronRight size={14} /> : null}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div>
            <span className={"connection-dot " + (health ? "connected" : "")} />
            {health ? "Backend conectado" : "Conectando…"}
          </div>
          <small>Local-first · Model-agnostic</small>
          <a
            href="https://github.com/fr4j4/system-one-arena"
            target="_blank"
            rel="noreferrer"
          >
            Repositorio <ArrowUpRight size={12} />
          </a>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div className="breadcrumb">
            Laboratorio <ChevronRight size={13} />
            <strong>{NAV.find(([id]) => id === page)?.[1]}</strong>
          </div>
          <div className="topbar-meta">
            <span className="version-badge">PROTOCOL 1.0</span>
            <span>Estados → decisiones → acciones</span>
            <CircleHelp size={17} />
          </div>
        </header>
        {error ? (
          <div role="alert" className="error-banner">
            <span>{error}</span>
            <button aria-label="Cerrar error" onClick={() => setError("")}>
              <X size={17} />
            </button>
          </div>
        ) : null}
        {page === "arena" ? (
          <div className="arena-page">
            <div className="page-heading">
              <div>
                <span className="eyebrow">
                  <Activity size={13} /> OBSERVA CADA DECISIÓN
                </span>
                <h1>La inteligencia, en acción.</h1>
                <p>
                  Elige un entorno. Conecta un modelo. Mira qué decide y cuánto
                  tarda.
                </p>
              </div>
              <button
                className="quiet-button"
                onClick={() => setPage("benchmarks")}
              >
                <BarChart3 size={16} /> Comparación controlada{" "}
                <ArrowUpRight size={14} />
              </button>
            </div>
            <div className="scenario-heading">
              <div className="segmented">
                <button
                  className={category === "game" ? "active" : ""}
                  onClick={() => setCategory("game")}
                >
                  Juegos <span>6</span>
                </button>
                <button
                  className={category === "business" ? "active" : ""}
                  onClick={() => setCategory("business")}
                >
                  Decisiones <span>9</span>
                </button>
              </div>
              <span className="muted">
                Estados estructurados · sin visión artificial
              </span>
            </div>
            <div className="scenario-grid">
              {scenarios
                .filter((s) => s.kind === category)
                .map((s) => (
                  <button
                    key={s.id}
                    className={
                      "scenario-card " + (scenario === s.id ? "selected" : "")
                    }
                    onClick={() => selectScenario(s.id)}
                  >
                    <span className="scenario-icon">{ICONS[s.id]}</span>
                    <strong>{s.name}</strong>
                    <small>{s.category}</small>
                    {scenario === s.id ? (
                      <Check size={13} className="scenario-check" />
                    ) : null}
                  </button>
                ))}
            </div>
            <section className="experiment-config">
              <div className="config-title">
                <span>
                  <SlidersHorizontal size={16} /> Configuración del experimento
                </span>
                <button
                  onClick={() => setAdvanced(!advanced)}
                  aria-expanded={advanced}
                >
                  <Settings2 size={14} />
                  {advanced ? "Menos opciones" : "Avanzado"}
                </button>
              </div>
              <div className="config-row">
                <label>
                  Proveedor
                  <select
                    aria-label="Proveedor"
                    value={provider}
                    onChange={(e) => setProvider(e.target.value)}
                  >
                    {providers.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.id === "simulated"
                          ? "Simulador · sin IA"
                          : p.id === "reference"
                            ? "Referencia · heurística"
                            : p.id === "random"
                              ? "Azar · sin IA"
                              : p.id.toUpperCase()}
                        {!p.configured ? " · configurar" : ""}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Reloj
                  <select
                    value={mode}
                    onChange={(e) => setMode(e.target.value)}
                  >
                    <option value="realtime">Tiempo real</option>
                    <option value="step">Paso a paso</option>
                  </select>
                </label>
                <label>
                  Presupuesto
                  <input
                    aria-label="Presupuesto en milisegundos"
                    type="number"
                    min="10"
                    max="60000"
                    value={budget}
                    onChange={(e) => setBudget(+e.target.value)}
                  />
                  <span className="input-unit">ms</span>
                </label>
                <label>
                  Frecuencia
                  <input
                    aria-label="Frecuencia de decisiones"
                    type="number"
                    min="1"
                    max="30"
                    value={hz}
                    onChange={(e) => setHz(+e.target.value)}
                  />
                  <span className="input-unit">Hz</span>
                </label>
                <button
                  className="primary start-button"
                  onClick={start}
                  disabled={loading || !providers.length}
                >
                  <Play size={16} fill="currentColor" />
                  {loading
                    ? "Iniciando…"
                    : runs.length
                      ? "Nueva ejecución"
                      : "Iniciar ejecución"}
                </button>
              </div>
              {advanced ? (
                <div className="advanced-options">
                  <label>
                    Comparar en vivo
                    <select
                      value={compare}
                      onChange={(e) => setCompare(e.target.value)}
                    >
                      <option value="">Un solo proveedor</option>
                      {providers
                        .filter((p) => p.id !== provider)
                        .map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.id}
                          </option>
                        ))}
                    </select>
                  </label>
                  <label>
                    Semilla
                    <input
                      type="number"
                      value={seed}
                      min="0"
                      onChange={(e) => setSeed(+e.target.value)}
                    />
                  </label>
                  <label>
                    Velocidad del mundo
                    <select
                      value={speed}
                      onChange={(e) => setSpeed(+e.target.value)}
                    >
                      {[0.1, 0.25, 0.5, 1, 1.5, 2, 3].map((n) => (
                        <option key={n} value={n}>
                          {n}×
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Antigüedad máxima (ms)
                    <input
                      type="number"
                      value={age}
                      min="10"
                      max="60000"
                      onChange={(e) => setAge(+e.target.value)}
                    />
                  </label>
                  <label>
                    Duración máxima (s)
                    <input
                      type="number"
                      min="1"
                      max="3600"
                      value={seconds}
                      onChange={(e) => setSeconds(+e.target.value)}
                    />
                  </label>
                  <label>
                    Representación
                    <select
                      value={representation}
                      onChange={(e) => setRepresentation(e.target.value)}
                    >
                      <option value="direct">Estado directo</option>
                      <option value="enriched">Estado enriquecido</option>
                    </select>
                  </label>
                  <label>
                    Control
                    <select
                      value={controller}
                      onChange={(e) => setController(e.target.value)}
                    >
                      <option value="model">Proveedor</option>
                      <option value="human">Humano · juegos</option>
                    </select>
                  </label>
                  {scenario === "tetris" ? (
                    <label>
                      Control de Tetris
                      <select
                        value={tetris}
                        onChange={(e) => setTetris(e.target.value)}
                      >
                        <option value="movement">Movimientos</option>
                        <option value="placement">Colocación final</option>
                      </select>
                    </label>
                  ) : null}
                  {scenario === "hierarchy" ? (
                    <label>
                      Clasificación
                      <select
                        value={hierarchy}
                        onChange={(e) => setHierarchy(e.target.value)}
                      >
                        <option value="tree">Jerárquica</option>
                        <option value="flat">Plana</option>
                      </select>
                    </label>
                  ) : null}
                </div>
              ) : null}
              <div className="config-foot">
                <span className="status-dot" />
                {provider === "simulated"
                  ? "Simulador: heurística con 35 ms añadidos. No es un modelo de IA."
                  : provider === "reference" || provider === "random"
                    ? "Control de referencia sin llamadas a un modelo."
                    : providers.find((p) => p.id === provider)?.description}
                {compare ? (
                  <span> · Misma semilla; trayectorias independientes.</span>
                ) : null}
                {datasets[scenario] ? (
                  <span>
                    {" "}
                    · Dataset propio: {datasets[scenario].length} casos
                  </span>
                ) : null}
              </div>
            </section>
            <div className="arena-section-title">
              <h2>
                {chosen?.name ?? "Arena"} <span>{chosen?.description}</span>
              </h2>
              <span className="live-label">
                <i /> LIVE INSPECTOR
              </span>
            </div>
            {runs.length ? (
              <div
                className={"runs-grid " + (runs.length > 1 ? "comparison" : "")}
              >
                {runs.map((run) => (
                  <RunPanel key={run.id} initial={run} onError={onError} />
                ))}
              </div>
            ) : (
              <div className="idle-layout">
                <div className="idle-scene">
                  <div className="idle-scene-header">
                    <span>{chosen?.name}</span>
                    <small>VISTA PREVIA · SIN INFERENCIA</small>
                  </div>
                  {chosen?.kind === "game" ? (
                    <GameCanvas state={preview?.state} />
                  ) : (
                    <div className="idle-document">
                      <span>ENTRADA DE EJEMPLO</span>
                      <blockquote>
                        {preview?.state?.text ??
                          "Selecciona un escenario de decisiones"}
                      </blockquote>
                    </div>
                  )}
                  <div className="idle-scene-bottom">
                    <span>Semilla {seed}</span>
                    <span>
                      Inicia una ejecución para observar decisiones reales{" "}
                      <ChevronRight size={13} />
                    </span>
                  </div>
                </div>
                <aside className="idle-inspector">
                  <span className="eyebrow">DEL ESTADO A LA ACCIÓN</span>
                  <h3>
                    Una decisión.
                    <br />
                    Toda su trayectoria.
                  </h3>
                  <div className="pipeline">
                    {[
                      ["Entrada", "El estado que recibe el modelo"],
                      ["Inferencia", "Tiempo de llamada y cola"],
                      ["Resultado", "Opciones y probabilidades"],
                      ["Acción", "Aplicada, tardía o descartada"],
                    ].map(([title, desc], i) => (
                      <div key={title}>
                        <span>{i + 1}</span>
                        <div>
                          <strong>{title}</strong>
                          <p>{desc}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="info-note">
                    <Zap size={16} />
                    <p>
                      La UI sigue viva mientras el modelo responde. El mundo
                      tampoco espera.
                    </p>
                  </div>
                </aside>
              </div>
            )}
            <footer className="arena-footer">
              <Terminal size={13} />
              <span>
                Sin razonamiento inventado. Solo estados, resultados y tiempos
                observados.
              </span>
              <button onClick={() => setPage("providers")}>
                Conectar otro modelo <Plus size={13} />
              </button>
            </footer>
          </div>
        ) : (
          <Suspense
            fallback={<div className="workspace-page">Cargando vista…</div>}
          >
            {page === "workflow" ? (
              <WorkflowEditor
                graph={graph}
                onGraph={setGraph}
                onError={onError}
              />
            ) : page === "datasets" ? (
              <Datasets
                scenarios={scenarios}
                onDataset={(name, items) =>
                  setDatasets((old) => ({ ...old, [name]: items }))
                }
                onError={onError}
              />
            ) : page === "benchmarks" ? (
              <Benchmarks
                scenarios={scenarios}
                providers={providers}
                onError={onError}
              />
            ) : page === "history" ? (
              <History onError={onError} />
            ) : (
              <section className="workspace-page">
                <div className="section-heading">
                  <div>
                    <span className="eyebrow">MODELOS INTERCAMBIABLES</span>
                    <h2>Un protocolo. Más posibilidades.</h2>
                    <p>
                      Las credenciales permanecen en el backend. Cada adaptador
                      declara lo que puede medir.
                    </p>
                  </div>
                </div>
                <div className="provider-cards">
                  {providers.map((p) => (
                    <article key={p.id}>
                      <span
                        className={
                          "provider-badge " + (p.configured ? "ready" : "")
                        }
                      >
                        {p.configured
                          ? "Configurado"
                          : "Requiere configuración"}
                      </span>
                      <h3>{p.id}</h3>
                      <p>{p.description}</p>
                      <ul>
                        <li>Choice · Ordinal · Probabilidad binaria</li>
                        <li>
                          {p.probabilities
                            ? "Distribuciones disponibles"
                            : "Sin probabilidades nativas"}
                        </li>
                        <li>
                          {p.internal_timings
                            ? "Instrumentación local de inferencia"
                            : "Tiempo de llamada observable"}
                        </li>
                      </ul>
                      {p.id === "laya" ? (
                        <pre>
                          {
                            "uv sync --extra laya\nLAYA_ENABLED=true\nLAYA_DEVICE=cuda\nLAYA_CHECKPOINT=multilingual"
                          }
                        </pre>
                      ) : p.id === "jev" ? (
                        <pre>{"TYPESAFE_API_KEY=…\nJEV_MODEL=jev-latest"}</pre>
                      ) : p.id === "generic" ? (
                        <pre>
                          {
                            "GENERIC_BASE_URL=…/v1\nGENERIC_MODEL=…\nGENERIC_API_KEY=…"
                          }
                        </pre>
                      ) : null}
                    </article>
                  ))}
                </div>
                <div className="info-note">
                  Reinicia el backend después de cambiar .env. La disponibilidad
                  de CUDA y los pesos se verifica al preparar una ejecución.
                </div>
                <details>
                  <summary>Entorno de ejecución</summary>
                  <pre>{JSON.stringify(health?.hardware, null, 2)}</pre>
                </details>
              </section>
            )}
          </Suspense>
        )}
      </main>
    </div>
  );
}
