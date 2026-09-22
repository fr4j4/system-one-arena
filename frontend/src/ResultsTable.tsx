import { useMemo, useState } from "react";
import { download, ms, pct } from "./types";

export function prediction(answer: any) {
  return answer?.type === "boolean_probability"
    ? Number(answer.value >= 0.5)
    : answer?.type === "ordinal"
      ? (() => {
          const lower = Math.floor(answer.value);
          return answer.value - lower === 0.5
            ? lower + (lower % 2)
            : Math.round(answer.value);
        })()
      : answer?.value;
}
export function verdict(row: any) {
  if (row.status === "error") return "error";
  const keys = Object.keys(row.expected ?? {}).filter((k) => row.answers?.[k]);
  if (!keys.length) return "unlabeled";
  return keys.every((k) =>
    (Array.isArray(row.expected[k])
      ? row.expected[k]
      : [row.expected[k]]
    ).includes(prediction(row.answers[k])),
  )
    ? "correct"
    : "incorrect";
}
const statusLabels: Record<string, string> = {
  correct: "Correcto",
  incorrect: "Incorrecto",
  error: "Fallo técnico",
  unlabeled: "Sin referencia",
};
const titles: Record<string, string> = {
  department: "Equipo",
  priority: "Prioridad",
  escalate: "Escalar",
  intent: "Intención",
  reply: "Responder",
  spam: "Spam",
  phishing: "Phishing",
  action: "Acción",
  category: "Categoría",
  subcategory: "Subcategoría",
  severity: "Severidad",
  team: "Equipo",
  tool: "Herramienta",
  relevant: "Relevante",
  anomaly: "Anomalía",
};
const words: Record<string, string> = {
  billing: "Facturación",
  technical: "Técnico",
  sales: "Ventas",
  other: "Otros",
  request: "Solicitud",
  information: "Información",
  promotion: "Promoción",
  allow: "Permitir",
  review: "Revisar",
  block: "Bloquear",
  search: "Buscar",
  calculator: "Calculadora",
  calendar: "Calendario",
  human: "Humano",
  platform: "Plataforma",
  security: "Seguridad",
  support: "Soporte",
};
export function display(value: any): string {
  if (Array.isArray(value)) return value.map(display).join(" / ");
  return words[String(value)] ?? String(value ?? "—");
}
function decisionLabel(
  value: any,
  type: string | undefined,
  key: string,
): string {
  if (Array.isArray(value))
    return value.map((v) => decisionLabel(v, type, key)).join(" / ");
  if (value == null) return "—";
  if (type === "boolean_probability") return Number(value) ? "Sí" : "No";
  if (type === "ordinal" && key === "priority")
    return ["Normal", "Atención", "Alta"][Number(value)] ?? display(value);
  if (type === "ordinal" && key === "severity")
    return (
      ["Sin impacto", "Degradación", "Caída total"][Number(value)] ??
      display(value)
    );
  return display(value);
}
function probability(a: any) {
  if (a.type === "boolean_probability") return `${pct(a.value)} sí`;
  return a.probabilities?.[String(a.value)] != null
    ? pct(a.probabilities[String(a.value)])
    : "—";
}
export default function ResultsTable({
  rows,
  total,
  name = "resultados",
}: {
  rows: any[];
  total?: number;
  name?: string;
}) {
  const [query, setQuery] = useState(""),
    [filter, setFilter] = useState("all"),
    [category, setCategory] = useState("all"),
    [difficulty, setDifficulty] = useState("all"),
    [order, setOrder] = useState("original"),
    [page, setPage] = useState(0),
    [selected, setSelected] = useState<string>();
  const keys = useMemo(
    () => [...new Set(rows.flatMap((r) => Object.keys(r.answers ?? {})))],
    [rows],
  );
  const categories = useMemo(
    () =>
      [
        ...new Set(
          rows.flatMap((r) =>
            Object.values(r.answers ?? {}).map((a: any) =>
              String(prediction(a)),
            ),
          ),
        ),
      ].sort(),
    [rows],
  );
  const filtered = useMemo(() => {
    const result = rows.filter(
      (r) =>
        (filter === "all" || verdict(r) === filter) &&
        (difficulty === "all" || r.metadata?.difficulty === difficulty) &&
        (category === "all" ||
          Object.values(r.answers ?? {}).some(
            (a: any) => String(prediction(a)) === category,
          )) &&
        JSON.stringify([r.id, r.state])
          .toLowerCase()
          .includes(query.toLowerCase()),
    );
    if (order === "latency")
      result.sort((a, b) => (b.latency_ms ?? 0) - (a.latency_ms ?? 0));
    if (order === "id") result.sort((a, b) => a.id.localeCompare(b.id));
    return result;
  }, [rows, filter, difficulty, category, query, order]);
  const currentPage = Math.min(
    page,
    Math.max(0, Math.ceil(filtered.length / 25) - 1),
  );
  const detail = rows.find((r) => r.id === selected);
  const counts = rows.reduce(
    (a, r) => {
      const v = verdict(r);
      a[v] = (a[v] ?? 0) + 1;
      return a;
    },
    {} as Record<string, number>,
  );
  const judged = (counts.correct ?? 0) + (counts.incorrect ?? 0);
  const exportCSV = () => {
    const quote = (v: any) =>
      '"' +
      String(v ?? "")
        .replace(/^[=+@-]/, "'$&")
        .replaceAll('"', '""') +
      '"';
    const header = [
      "id",
      "entrada",
      ...keys.flatMap((k) => [k, k + "_esperado", k + "_probabilidad"]),
      "evaluación",
      "latencia_ms",
      "error",
      "ruta",
    ];
    const data = filtered.map((r) => [
      r.id,
      r.state.text ?? JSON.stringify(r.state),
      ...keys.flatMap((k) => [
        prediction(r.answers[k]),
        display(r.expected?.[k]),
        r.answers[k] ? probability(r.answers[k]) : "",
      ]),
      statusLabels[verdict(r)],
      r.latency_ms,
      r.error,
      r.path?.join(" → "),
    ]);
    download(
      name + ".csv",
      [header, ...data].map((r) => r.map(quote).join(",")).join("\n"),
    );
  };
  return (
    <section className="results-workspace" aria-label="Resultados por caso">
      <div className="results-summary">
        <strong>
          {rows.length} / {total ?? rows.length} procesados
        </strong>
        <span>
          {counts.correct ?? 0} correctos · {counts.incorrect ?? 0} incorrectos
          · {counts.error ?? 0} fallos técnicos
        </span>
        <span>
          Acierto por caso:{" "}
          {judged
            ? pct((counts.correct ?? 0) / judged)
            : "Sin etiquetas evaluables"}
        </span>
      </div>
      <div className="question-accuracy" aria-label="Acierto por decisión">
        {keys.map((key) => {
          const eligible = rows.filter(
            (r) =>
              r.status !== "error" &&
              r.answers?.[key] &&
              r.expected?.[key] !== undefined,
          );
          const correct = eligible.filter((r) =>
            (Array.isArray(r.expected[key])
              ? r.expected[key]
              : [r.expected[key]]
            ).includes(prediction(r.answers[key])),
          ).length;
          return (
            <span key={key}>
              {titles[key] ?? key}:{" "}
              <b>
                {eligible.length
                  ? pct(correct / eligible.length)
                  : "Sin referencia"}
              </b>{" "}
              ({eligible.length} evaluadas)
            </span>
          );
        })}
      </div>
      <div className="results-toolbar">
        <input
          aria-label="Buscar casos"
          placeholder="Buscar texto o ID…"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setPage(0);
          }}
        />
        <select
          aria-label="Filtrar evaluación"
          value={filter}
          onChange={(e) => {
            setFilter(e.target.value);
            setPage(0);
          }}
        >
          <option value="all">Todas las evaluaciones</option>
          {Object.entries(statusLabels).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <select
          aria-label="Filtrar categoría"
          value={category}
          onChange={(e) => {
            setCategory(e.target.value);
            setPage(0);
          }}
        >
          <option value="all">Todas las decisiones</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {display(c)}
            </option>
          ))}
        </select>
        <select
          aria-label="Filtrar dificultad"
          value={difficulty}
          onChange={(e) => {
            setDifficulty(e.target.value);
            setPage(0);
          }}
        >
          <option value="all">Todas las dificultades</option>
          {["claro", "difícil", "ambiguo"].map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
        <select
          aria-label="Ordenar resultados"
          value={order}
          onChange={(e) => {
            setOrder(e.target.value);
            setPage(0);
          }}
        >
          <option value="original">Orden de procesamiento</option>
          <option value="latency">Mayor latencia</option>
          <option value="id">ID del caso</option>
        </select>
        <button onClick={exportCSV}>Exportar CSV</button>
        <button
          onClick={() =>
            download(
              name + ".jsonl",
              filtered.map((r) => JSON.stringify(r)).join("\n"),
            )
          }
        >
          Exportar JSONL
        </button>
      </div>
      <div className="results-scroll">
        <table className="case-table">
          <thead>
            <tr>
              <th>Caso</th>
              <th>Entrada</th>
              {keys.map((k) => (
                <th key={k}>
                  {titles[k] ?? k}
                  <small>Decisión / esperado / probabilidad</small>
                </th>
              ))}
              <th>Evaluación</th>
              <th>Latencia</th>
              <th>Ruta / salida</th>
            </tr>
          </thead>
          <tbody>
            {filtered
              .slice(currentPage * 25, (currentPage + 1) * 25)
              .map((r) => (
                <tr key={r.id}>
                  <td>
                    <button onClick={() => setSelected(r.id)}>{r.id}</button>
                    <small>{r.metadata?.difficulty}</small>
                  </td>
                  <td className="case-input">
                    {String(r.state.text ?? JSON.stringify(r.state)).slice(
                      0,
                      160,
                    )}
                  </td>
                  {keys.map((k) => (
                    <td key={k}>
                      <b>
                        {decisionLabel(
                          prediction(r.answers?.[k]),
                          r.answers?.[k]?.type,
                          k,
                        )}
                      </b>
                      <small>
                        Esperado:{" "}
                        {decisionLabel(
                          r.expected?.[k],
                          r.answers?.[k]?.type,
                          k,
                        )}
                      </small>
                      <small>
                        Prob.:{" "}
                        {r.answers?.[k] ? probability(r.answers[k]) : "—"}
                      </small>
                    </td>
                  ))}
                  <td>
                    <span className={"verdict " + verdict(r)}>
                      {statusLabels[verdict(r)]}
                    </span>
                  </td>
                  <td>
                    {ms(r.latency_ms)} ms<small>{r.calls ?? 1} consultas</small>
                  </td>
                  <td>
                    {r.output ?? "—"}
                    <small>{r.path?.join(" → ")}</small>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
        {!filtered.length && (
          <p className="muted">Todavía no hay resultados para estos filtros.</p>
        )}
      </div>
      <div className="results-pagination">
        <button
          disabled={!currentPage}
          onClick={() => setPage(currentPage - 1)}
        >
          Anterior
        </button>
        <span>
          {filtered.length} casos · Página {currentPage + 1} de{" "}
          {Math.max(1, Math.ceil(filtered.length / 25))}
        </span>
        <button
          disabled={(currentPage + 1) * 25 >= filtered.length}
          onClick={() => setPage(currentPage + 1)}
        >
          Siguiente
        </button>
      </div>
      {detail && (
        <div
          className="case-detail"
          role="region"
          aria-label="Detalle del caso"
        >
          <button onClick={() => setSelected(undefined)}>Cerrar detalle</button>
          <h3>{detail.id}</h3>
          <p className="case-full-text">
            {detail.state.text ?? JSON.stringify(detail.state)}
          </p>
          <p>
            {detail.error ??
              detail.metadata?.rationale ??
              "Sin explicación de referencia."}
          </p>
          <p>
            {detail.metadata?.source} · {detail.metadata?.version} · Familia:{" "}
            {detail.metadata?.family ?? "—"}
          </p>
          <p>
            La explicación es del dataset; no representa razonamiento interno
            del modelo.
          </p>
          <pre>
            {JSON.stringify(
              {
                entrada: detail.state,
                decisiones: detail.answers,
                esperado: detail.expected,
                ruta: detail.path,
                salida: detail.output,
              },
              null,
              2,
            )}
          </pre>
        </div>
      )}
      <p className="results-note">
        Booleanos: umbral 0,5. Ordinales: redondeo. Alternativas de referencia:
        cualquiera es válida. El acierto excluye fallos técnicos y casos sin
        referencia; estos se cuentan por separado. Latencia: suma de llamadas
        del caso, incluida red.
      </p>
    </section>
  );
}
