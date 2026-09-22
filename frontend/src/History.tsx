import { useEffect, useState } from "react";
import { Download, Play, Pause, RefreshCw } from "lucide-react";
import { api, ms, type Event, type Run } from "./types";
import GameCanvas from "./GameCanvas";
import ResultsTable from "./ResultsTable";
import { Distribution } from "./RunPanel";
export default function History({ onError }: { onError: (s: string) => void }) {
  const [runs, setRuns] = useState<Run[]>([]),
    [selected, setSelected] = useState<Run>(),
    [events, setEvents] = useState<Event[]>([]),
    [position, setPosition] = useState(0),
    [playing, setPlaying] = useState(false),
    [loading, setLoading] = useState(false);
  const refresh = () =>
    api<Run[]>("/runs")
      .then(setRuns)
      .catch((e) => onError(String(e)));
  useEffect(() => {
    refresh();
  }, []);
  const load = async (run: Run) => {
    setPlaying(false);
    setLoading(true);
    try {
      let all: Event[] = [],
        after = 0;
      while (true) {
        const batch = await api<Event[]>(
          `/runs/${run.id}/events?after=${after}&limit=10000`,
        );
        all = all.concat(batch);
        if (batch.length < 10000) break;
        after = batch.at(-1)!.seq;
      }
      setSelected(run);
      setEvents(all);
      setPosition(0);
    } catch (e) {
      onError(String(e));
    } finally {
      setLoading(false);
    }
  };
  const snapshots = events.filter((e) => e.kind === "snapshot");
  useEffect(() => {
    if (!playing) return;
    let start = performance.now(),
      base = snapshots[position]?.elapsed_ms ?? 0;
    const id = window.setInterval(() => {
      const elapsed = base + performance.now() - start;
      setPosition((old) => {
        let next = old;
        while (
          next + 1 < snapshots.length &&
          snapshots[next + 1].elapsed_ms <= elapsed
        )
          next++;
        if (next >= snapshots.length - 1) setPlaying(false);
        return next;
      });
    }, 30);
    return () => clearInterval(id);
  }, [playing, events]);
  const snap = snapshots[position];
  const result = events
    .filter((e) => e.kind === "completed" && e.seq <= (snap?.seq ?? 0))
    .at(-1)?.result;
  return (
    <section className="workspace-page">
      <div className="section-heading">
        <div>
          <span className="eyebrow">REGISTRO DE EXPERIMENTOS</span>
          <h2>Vuelve a la decisión exacta.</h2>
          <p>
            El replay usa los estados guardados. No vuelve a llamar al
            proveedor.
          </p>
        </div>
        <button onClick={refresh}>
          <RefreshCw size={15} /> Actualizar
        </button>
      </div>
      <div className="history-layout">
        <div className="history-list">
          {runs.map((r) => (
            <button
              key={r.id}
              className={selected?.id === r.id ? "selected" : ""}
              onClick={() => load(r)}
            >
              <strong>
                {r.config.scenario}
                <span>{r.config.provider}</span>
              </strong>
              <small>
                {new Date(r.created_at).toLocaleString()} · {r.status}
              </small>
              <span className="history-latency">
                p95 {ms(r.metrics.provider_ms.p95)} ms
              </span>
            </button>
          ))}
          {!runs.length ? (
            <p className="muted">Las ejecuciones aparecerán aquí.</p>
          ) : null}
        </div>
        <div className="replay-panel">
          {loading ? (
            <p>Cargando registro…</p>
          ) : selected ? (
            <>
              <header>
                <h3>
                  {selected.config.scenario} / {selected.config.provider}
                </h3>
                <a href={"/api/runs/" + selected.id + "/export"}>
                  <Download size={16} /> Exportar
                </a>
              </header>
              {snap?.state?.board ||
              ["snake", "pong", "fighting", "space-invaders"].includes(
                snap?.state?.scenario,
              ) ? (
                <GameCanvas state={snap?.state} />
              ) : (
                <div className="replay-document">
                  <p>{snap?.state?.text ?? "Sin snapshots disponibles"}</p>
                </div>
              )}
              <div className="replay-controls">
                <button
                  aria-label={playing ? "Pausar replay" : "Reproducir replay"}
                  onClick={() => {
                    if (position === snapshots.length - 1) setPosition(0);
                    setPlaying(!playing);
                  }}
                >
                  {playing ? <Pause size={16} /> : <Play size={16} />}
                </button>
                <input
                  aria-label="Posición del replay"
                  type="range"
                  min="0"
                  max={Math.max(0, snapshots.length - 1)}
                  value={position}
                  onChange={(e) => {
                    setPlaying(false);
                    setPosition(+e.target.value);
                  }}
                />
                <span>{((snap?.elapsed_ms ?? 0) / 1000).toFixed(1)} s</span>
              </div>
              {events.some((e) => e.row) && (
                <ResultsTable
                  rows={[
                    ...new Map(
                      events.filter((e) => e.row).map((e) => [e.row.id, e.row]),
                    ).values(),
                  ]}
                  name={selected.id}
                />
              )}
              <Distribution result={result} />
              <details>
                <summary>Manifiesto de ejecución</summary>
                <pre>{JSON.stringify(selected, null, 2)}</pre>
              </details>
            </>
          ) : (
            <div className="empty-small">
              Selecciona una ejecución para inspeccionarla.
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
