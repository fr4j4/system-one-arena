import { useEffect, useState } from "react";
import { Download, Play, Square } from "lucide-react";
import {
  api,
  download,
  ms,
  pct,
  post,
  terminal,
  type Provider,
  type Scenario,
  type Quality,
} from "./types";
import { Metric } from "./RunPanel";
export function QualityView({ q }: { q: Quality | undefined | null }) {
  return !q ? (
    <p className="muted">Sin etiquetas evaluables todavía.</p>
  ) : (
    <>
      <div className="metric-grid">
        <Metric name="Accuracy" value={pct(q.accuracy)} unit="" />
        <Metric name="Macro F1" value={pct(q.macro_f1)} unit="" />
        <Metric name="Brier ↓" value={q.brier?.toFixed(3) ?? "—"} unit="" />
        <Metric name="ECE ↓" value={q.ece?.toFixed(3) ?? "—"} unit="" />
      </div>
      <h4>Probabilidad vs. acierto observado</h4>
      <div className="calibration">
        {q.calibration.map((b, i) => (
          <div
            key={i}
            title={`${b.count} casos · probabilidad ${pct(b.probability)} · acierto ${pct(b.accuracy)}`}
          >
            <div className="calibration-bars">
              <i style={{ height: (b.probability ?? 0) * 100 + "%" }} />
              <b style={{ height: (b.accuracy ?? 0) * 100 + "%" }} />
            </div>
            <small>{i * 10}</small>
          </div>
        ))}
      </div>
      <p className="chart-legend">
        <i />
        Probabilidad <b />
        Acierto · intervalos del 10%
      </p>
      <details className="confusion">
        <summary>
          Matrices de confusión ({q.count} respuestas evaluadas)
        </summary>
        {Object.entries(q.confusion).map(([key, m]) => (
          <div key={key}>
            <h4>{key}</h4>
            <table>
              <thead>
                <tr>
                  <th>Real → Predicción</th>
                  <th>Casos</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(m).flatMap(([real, preds]) =>
                  Object.entries(preds).map(([pred, n]) => (
                    <tr key={real + pred}>
                      <td>
                        {real} → {pred}
                      </td>
                      <td>{n}</td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </div>
        ))}
      </details>
    </>
  );
}
export default function Benchmarks({
  scenarios,
  providers,
  onError,
}: {
  scenarios: Scenario[];
  providers: Provider[];
  onError: (s: string) => void;
}) {
  const [scenario, setScenario] = useState("snake"),
    [selected, setSelected] = useState(["reference", "simulated"]),
    [mode, setMode] = useState("corpus"),
    [samples, setSamples] = useState(500),
    [warmup, setWarmup] = useState(20),
    [episodes, setEpisodes] = useState(30),
    [budget, setBudget] = useState(100),
    [job, setJob] = useState<any>(),
    [busy, setBusy] = useState(false),
    [temperature, setTemperature] = useState(1),
    [threshold, setThreshold] = useState(0.5),
    [evaluation, setEvaluation] = useState<any>();
  useEffect(() => {
    if (!job || terminal(job.status)) return;
    let stopped = false;
    const id = window.setInterval(
      () =>
        api<any>("/benchmarks/" + job.id)
          .then((j) => {
            if (!stopped) setJob(j);
          })
          .catch((e) => onError(String(e))),
      1200,
    );
    return () => {
      stopped = true;
      clearInterval(id);
    };
  }, [job?.id, job?.status]);
  const start = async () => {
    setBusy(true);
    setEvaluation(undefined);
    try {
      setJob(
        await post("/benchmarks", {
          scenario,
          providers: selected,
          mode,
          samples,
          warmup,
          episodes,
          budget_ms: budget,
        }),
      );
    } catch (e) {
      onError(String(e));
    } finally {
      setBusy(false);
    }
  };
  const active = job?.status === "running";
  return (
    <section className="workspace-page">
      <div className="section-heading">
        <div>
          <span className="eyebrow">COMPARACIÓN CONTROLADA</span>
          <h2>Medir antes de concluir.</h2>
          <p>
            Entradas idénticas para comparar decisiones. Episodios
            independientes para observar sus consecuencias.
          </p>
        </div>
        <button
          className="primary"
          disabled={busy || active || !selected.length}
          onClick={start}
        >
          <Play size={15} /> Iniciar benchmark
        </button>
      </div>
      <div className="benchmark-controls">
        <label>
          Escenario
          <select
            value={scenario}
            onChange={(e) => setScenario(e.target.value)}
          >
            {scenarios.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Experimento
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="corpus">Mismos estados</option>
            <option value="episodes">Episodios por semilla</option>
          </select>
        </label>
        {mode === "corpus" ? (
          <>
            <label>
              Mediciones
              <input
                type="number"
                min="1"
                max="10000"
                value={samples}
                onChange={(e) => setSamples(+e.target.value)}
              />
            </label>
            <label>
              Calentamiento
              <input
                type="number"
                min="0"
                max="100"
                value={warmup}
                onChange={(e) => setWarmup(+e.target.value)}
              />
            </label>
          </>
        ) : (
          <label>
            Episodios
            <input
              type="number"
              min="1"
              max="100"
              value={episodes}
              onChange={(e) => setEpisodes(+e.target.value)}
            />
          </label>
        )}
        <label>
          Presupuesto (ms)
          <input
            type="number"
            min="10"
            max="60000"
            value={budget}
            onChange={(e) => setBudget(+e.target.value)}
          />
        </label>
      </div>
      <div className="provider-checks">
        {providers.map((p) => (
          <label key={p.id} className={!p.configured ? "unconfigured" : ""}>
            <input
              type="checkbox"
              checked={selected.includes(p.id)}
              disabled={!p.configured || active}
              onChange={(e) =>
                setSelected((old) =>
                  e.target.checked
                    ? [...old, p.id].slice(-4)
                    : old.filter((k) => k !== p.id),
                )
              }
            />
            <b>{p.id}</b>
            <span>{p.description}</span>
          </label>
        ))}
      </div>
      {job ? (
        <>
          <div className="benchmark-progress">
            <div>
              <strong>
                {job.status === "running"
                  ? "Evaluación en curso"
                  : job.status === "completed"
                    ? "Evaluación completada"
                    : job.status}
              </strong>
              <span>{Math.min(100, job.progress * 100).toFixed(0)}%</span>
            </div>
            <progress max="1" value={job.progress} />
            {active ? (
              <button
                onClick={() =>
                  post("/benchmarks/" + job.id + "/cancel", {}).catch((e) =>
                    onError(String(e)),
                  )
                }
              >
                <Square size={12} /> Cancelar al finalizar la llamada actual
              </button>
            ) : (
              <button
                onClick={() => download("benchmark-" + job.id + ".json", job)}
              >
                <Download size={15} /> Exportar resultados
              </button>
            )}
            {job.error ? <p className="inline-error">{job.error}</p> : null}
          </div>
          <div className="benchmark-results">
            {Object.entries(job.results ?? {}).map(
              ([provider, result]: [string, any]) => (
                <article className="result-card" key={provider}>
                  <h3>
                    {provider}
                    <small>{result.rows?.[0]?.model ?? ""}</small>
                  </h3>
                  {result.latency ? (
                    <>
                      <div className="metric-grid">
                        <Metric
                          name="p50"
                          value={ms(result.latency.p50)}
                          unit="ms"
                        />
                        <Metric
                          name="p95"
                          value={ms(result.latency.p95)}
                          unit="ms"
                        />
                        <Metric
                          name="p99"
                          value={ms(result.latency.p99)}
                          unit="ms"
                        />
                        <Metric
                          name="Deadline perdido"
                          value={pct(result.deadline_miss_rate)}
                          unit=""
                        />
                      </div>
                      <QualityView q={result.quality} />
                      <p className="muted">
                        {result.errors?.length ?? 0} errores ·{" "}
                        {result.rows?.length ?? 0} mediciones válidas
                      </p>
                      {result.errors?.length ? (
                        <details>
                          <summary>Ver errores</summary>
                          <pre>
                            {JSON.stringify(
                              result.errors.slice(0, 10),
                              null,
                              2,
                            )}
                          </pre>
                        </details>
                      ) : null}
                    </>
                  ) : (
                    <>
                      <p>{result.episodes?.length ?? 0} episodios terminados</p>
                      <Metric
                        name="Puntuación media"
                        value={ms(result.score?.mean)}
                        unit=""
                      />
                      <div className="episode-list">
                        {result.episodes?.map((e: any) => (
                          <a key={e.id} href={"/api/runs/" + e.id + "/export"}>
                            Semilla {e.config.seed}: {e.metrics.score ?? "—"} ·{" "}
                            {e.status}
                          </a>
                        ))}
                      </div>
                    </>
                  )}
                </article>
              ),
            )}
          </div>
          {terminal(job.status) && mode === "corpus" ? (
            <section className="calibration-lab">
              <h3>Explorar umbrales y calibración</h3>
              <p>
                La transformación es exploratoria; no ajusta parámetros sobre un
                conjunto de calibración independiente.
              </p>
              <div className="toolbar">
                <label>
                  Umbral binario {threshold.toFixed(2)}
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step=".05"
                    value={threshold}
                    onChange={(e) => setThreshold(+e.target.value)}
                  />
                </label>
                <label>
                  Temperatura {temperature.toFixed(2)}
                  <input
                    type="range"
                    min=".1"
                    max="4"
                    step=".1"
                    value={temperature}
                    onChange={(e) => setTemperature(+e.target.value)}
                  />
                </label>
                <button
                  onClick={async () => {
                    try {
                      const first: any = Object.values(job.results)[0];
                      setEvaluation(
                        await post("/evaluate", {
                          rows: first.rows ?? [],
                          threshold,
                          temperature,
                        }),
                      );
                    } catch (e) {
                      onError(String(e));
                    }
                  }}
                >
                  Evaluar primer proveedor
                </button>
              </div>
              {evaluation ? (
                <>
                  <p>Umbral ajustado</p>
                  <QualityView q={evaluation.raw} />
                  <p>Temperatura exploratoria</p>
                  <QualityView q={evaluation.temperature_preview} />
                </>
              ) : null}
            </section>
          ) : null}
        </>
      ) : (
        <div className="benchmark-empty">
          <div className="empty-lines">
            <i />
            <i />
            <i />
            <i />
          </div>
          <h3>No hay un ganador predeterminado.</h3>
          <p>
            Se ejecutará cada proveedor por separado. En juegos, la calidad del
            corpus indica acuerdo con la heurística, no una garantía de
            estrategia óptima.
          </p>
          <small>
            20 calentamientos + 500 mediciones · sin caché de respuestas
          </small>
        </div>
      )}
    </section>
  );
}
