import { useEffect, useState } from "react";
import { api, type Config, type Match } from "./types";
export function Laboratory({
  config,
  onWatch,
  onError,
}: {
  config: Config;
  onWatch: (m: Match) => void;
  onError: (s: string) => void;
}) {
  const [series, setSeries] = useState<any[]>([]),
    [pairs, setPairs] = useState(2),
    [pace, setPace] = useState("native"),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    let alive = true;
    const load = () =>
      api<any[]>("/series")
        .then((v) => {
          if (alive) setSeries(v);
        })
        .catch((e) => onError(String(e)));
    void load();
    const id = setInterval(load, 2000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [onError]);
  const start = async () => {
    setBusy(true);
    try {
      const match = {
        ...config,
        mode: "duel",
        pace,
        round_seconds: 30,
        best_of: 1,
        max_seconds: 180,
      };
      const job = await api("/series", { match, pairs });
      setSeries((s) => [job, ...s]);
    } catch (e) {
      onError(String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="laboratory">
      <div className="section-heading">
        <div>
          <span className="eyebrow">COMPARACIÓN CONTROLADA</span>
          <h2>El mismo desafío. Ambos lados.</h2>
        </div>
        <p>
          La segunda partida de cada par intercambia jugadores y personajes. Los
          resultados de latencia nativa y ventanas comunes se mantienen
          separados.
        </p>
      </div>
      <div className="series-config">
        <label>
          Pares de partidas
          <select value={pairs} onChange={(e) => setPairs(+e.target.value)}>
            {[1, 2, 5, 10, 20].map((n) => (
              <option key={n} value={n}>
                {n} pares · {n * 2} partidas
              </option>
            ))}
          </select>
        </label>
        <label>
          Ritmo de evaluación
          <select value={pace} onChange={(e) => setPace(e.target.value)}>
            <option value="native">Latencia nativa</option>
            <option value="equal_windows">Ventanas comunes · 800 ms</option>
          </select>
        </label>
        <button
          className="primary"
          disabled={
            busy || config.players.some((p) => p.controller === "human")
          }
          onClick={start}
        >
          Iniciar serie
        </button>
      </div>
      {config.players.some((p) => p.controller === "human") && (
        <p className="muted">
          Selecciona dos controladores automáticos en los slots para comparar
          modelos.
        </p>
      )}
      {series.map((job) => (
        <div className="series-card" key={job.id}>
          <header>
            <b>
              {job.config.match.players
                .map((p: any) => p.model_profile_id)
                .join(" vs ")}
            </b>
            <span>
              {job.status} · {job.results.length}/{job.config.pairs * 2}
            </span>
            <span>
              {job.config.match.pace === "native"
                ? "Latencia nativa"
                : "Ventanas de 800 ms"}
            </span>
            {job.current_id && (
              <button
                onClick={() =>
                  api<Match>("/matches/" + job.current_id)
                    .then(onWatch)
                    .catch((e) => onError(String(e)))
                }
              >
                Ver combate
              </button>
            )}
            {job.status === "running" && (
              <button
                onClick={() =>
                  api(`/series/${job.id}/stop`, {}).catch((e) =>
                    onError(String(e)),
                  )
                }
              >
                Detener serie
              </button>
            )}
          </header>
          {job.error && <p className="error-banner">{job.error}</p>}
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Par / lado</th>
                  <th>P1 / P2</th>
                  <th>Ganador</th>
                  <th>Daño</th>
                  <th>Energía gastada</th>
                  <th>Parries</th>
                  <th>Choques</th>
                  <th>p50 / p95 ms</th>
                  <th>Aplicadas / recibidas</th>
                  <th>Caducadas / errores</th>
                  <th>Replay</th>
                </tr>
              </thead>
              <tbody>
                {job.results.map((r: any) => (
                  <tr key={r.id}>
                    <td>
                      {r.pair} · {r.mirrored ? "Invertido" : "Original"}
                    </td>
                    <td>
                      {r.config.players
                        .map(
                          (p: any) => `${p.model_profile_id} · ${p.fighter_id}`,
                        )
                        .join(" / ")}
                    </td>
                    <td>
                      {r.state?.winner
                        ? r.config.players[Number(r.state.winner.slice(1)) - 1]
                            .model_profile_id
                        : "Empate"}
                    </td>
                    <td>
                      {r.state?.fighters
                        .map((f: any) => f.stats.damage)
                        .join(" / ")}
                    </td>
                    <td>
                      {r.state?.fighters
                        .map((f: any) => Math.round(f.stats.energy_spent))
                        .join(" / ")}
                    </td>
                    <td>
                      {r.state?.fighters
                        .map((f: any) => f.stats.parries)
                        .join(" / ")}
                    </td>
                    <td>
                      {r.state?.fighters
                        .map((f: any) => f.stats.clashes)
                        .join(" / ")}
                    </td>
                    <td>
                      {r.players
                        .map(
                          (p: any) =>
                            `${p.latency.p50?.toFixed(0) ?? "—"} / ${p.latency.p95?.toFixed(0) ?? "—"}`,
                        )
                        .join(" / ")}
                    </td>
                    <td>
                      {r.players
                        .map(
                          (p: any) =>
                            `${p.counts.applied ?? 0} / ${p.counts.completed ?? 0}`,
                        )
                        .join(" · ")}
                    </td>
                    <td>
                      {r.players
                        .map(
                          (p: any) =>
                            `${p.counts.expired ?? 0} / ${p.counts.errors ?? 0}`,
                        )
                        .join(" · ")}
                    </td>
                    <td>
                      <a href={`/api/v2/matches/${r.id}/export`}>JSONL</a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </section>
  );
}
