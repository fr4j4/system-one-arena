import { useEffect, useState } from "react";
import { api, ms, terminal, type Run } from "./types";
import { display, prediction } from "./ResultsTable";

export default function ComparisonTable({ runs }: { runs: Run[] }) {
  const [views, setViews] = useState<Run[]>([]),
    [onlyDifferent, setOnlyDifferent] = useState(false),
    [page, setPage] = useState(0);
  const ids = runs.map((r) => r.id).join(",");
  useEffect(() => {
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    async function update() {
      try {
        const next = await Promise.all(
          runs.map((r) => api<Run>("/runs/" + r.id)),
        );
        if (disposed) return;
        setViews(next);
        if (next.some((r) => !terminal(r.status)))
          timer = setTimeout(update, 1000);
      } catch {
        if (!disposed) timer = setTimeout(update, 2000);
      }
    }
    update();
    return () => {
      disposed = true;
      clearTimeout(timer);
    };
  }, [ids]);
  if (views.length !== 2) return null;
  const left = views[0],
    right = views[1];
  const rightRows = new Map((right.rows ?? []).map((r) => [r.id, r]));
  const pairs = (left.rows ?? []).map((l) => {
    const r = rightRows.get(l.id);
    const comparable = r && l.status !== "error" && r.status !== "error";
    const different =
      comparable &&
      [...new Set([...Object.keys(l.answers), ...Object.keys(r.answers)])].some(
        (k) => prediction(l.answers[k]) !== prediction(r.answers[k]),
      );
    return { l, r, different };
  });
  const rows = pairs.filter((p) => !onlyDifferent || p.different);
  const answer = (r: any) =>
    !r
      ? "Pendiente"
      : r.status === "error"
        ? "Fallo técnico"
        : Object.entries(r.answers)
            .map(([k, a]) => `${k}: ${display(prediction(a))}`)
            .join(" · ");
  const current = Math.min(page, Math.max(0, Math.ceil(rows.length / 25) - 1));
  return (
    <section className="results-workspace comparison-table">
      <h3>Comparación por caso</h3>
      <p>
        Misma muestra y orden. Las consultas simultáneas pueden compartir
        recursos; para medir latencias aisladas usa Experimentos.
      </p>
      <label>
        <input
          type="checkbox"
          checked={onlyDifferent}
          onChange={(e) => {
            setOnlyDifferent(e.target.checked);
            setPage(0);
          }}
        />{" "}
        Solo desacuerdos ({pairs.filter((p) => p.different).length})
      </label>
      <div className="results-scroll">
        <table className="case-table">
          <thead>
            <tr>
              <th>Caso</th>
              <th>{left.config.provider}</th>
              <th>{right.config.provider}</th>
              <th>Referencia</th>
              <th>Comparación</th>
            </tr>
          </thead>
          <tbody>
            {rows
              .slice(current * 25, (current + 1) * 25)
              .map(({ l, r, different }) => (
                <tr key={l.id}>
                  <td>
                    {l.id}
                    <small>{l.state.text?.slice(0, 100)}</small>
                  </td>
                  <td>
                    {answer(l)}
                    <small>{ms(l.latency_ms)} ms</small>
                  </td>
                  <td>
                    {answer(r)}
                    <small>{ms(r?.latency_ms)} ms</small>
                  </td>
                  <td>
                    {Object.entries(l.expected ?? {})
                      .map(([k, v]) => `${k}: ${display(v)}`)
                      .join(" · ") || "Sin referencia"}
                  </td>
                  <td>
                    {!r
                      ? "Pendiente"
                      : r.status === "error" || l.status === "error"
                        ? "No comparable"
                        : different
                          ? "Desacuerdo"
                          : "Coinciden"}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
      <div className="results-pagination">
        <button disabled={!current} onClick={() => setPage(current - 1)}>
          Anterior
        </button>
        <span>{rows.length} casos</span>
        <button
          disabled={(current + 1) * 25 >= rows.length}
          onClick={() => setPage(current + 1)}
        >
          Siguiente
        </button>
      </div>
    </section>
  );
}
