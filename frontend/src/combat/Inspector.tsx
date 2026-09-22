import { useState } from "react";
import type { Match } from "./types";
export function Inspector({ match, events }: { match: Match; events: any[] }) {
  const [player, setPlayer] = useState(0),
    [tab, setTab] = useState("decision");
  const p = match.players[player];
  const answer = p.last_result?.answers?.action;
  const probabilities = answer?.probabilities;
  return (
    <section className="inspector">
      <div className="inspector-head">
        <div>
          <span className="eyebrow">OBSERVABILIDAD</span>
          <h2>Detrás del movimiento</h2>
        </div>
        <div className="segmented">
          {match.players.map((s, i) => (
            <button
              key={i}
              className={i === player ? "selected" : ""}
              onClick={() => setPlayer(i)}
            >
              P{i + 1} · {s.controller === "human" ? "Tú" : s.model_profile_id}
            </button>
          ))}
        </div>
      </div>
      <div className="inspector-metrics">
        <div>
          <small>MODELO EFECTIVO</small>
          <b>
            {p.actual_model ??
              (p.controller === "human"
                ? "Control humano"
                : "Esperando respuesta")}
          </b>
        </div>
        <div>
          <small>LATENCIA P50 / P95</small>
          <b>
            {p.latency.p50?.toFixed(0) ?? "—"} /{" "}
            {p.latency.p95?.toFixed(0) ?? "—"} <em>ms</em>
          </b>
        </div>
        <div>
          <small>ACCIONES APLICADAS</small>
          <b>{p.counts.applied ?? 0}</b>
        </div>
        <div>
          <small>FUERA DE PLAZO / RECHAZADAS</small>
          <b>
            {p.counts.expired ?? 0} / {p.counts.rejected ?? 0}
          </b>
        </div>
      </div>
      <div className="inspector-tabs">
        {[
          ["decision", "Decisión"],
          ["timeline", "Timeline"],
          ["input", "Entrada"],
          ["output", "Respuesta"],
        ].map(([id, label]) => (
          <button
            key={id}
            className={tab === id ? "selected" : ""}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="inspector-content">
        {tab === "decision" ? (
          <>
            <div className="decision-title">
              <span>ÚLTIMA ELECCIÓN</span>
              <b>{answer?.value ?? "Esperando una decisión"}</b>
            </div>
            {probabilities ? (
              <div className="probabilities">
                {Object.entries(probabilities)
                  .sort((a: any, b: any) => b[1] - a[1])
                  .slice(0, 8)
                  .map(([id, value]) => (
                    <div key={id}>
                      <span>{id}</span>
                      <i>
                        <b style={{ width: Number(value) * 100 + "%" }} />
                      </i>
                      <strong>{(Number(value) * 100).toFixed(1)}%</strong>
                    </div>
                  ))}
              </div>
            ) : (
              <p className="muted">
                {p.controller === "human"
                  ? "Los comandos humanos se registran en la línea de tiempo."
                  : "El proveedor no ha entregado una distribución. No se estima confianza artificial."}
              </p>
            )}
            <p className="muted">
              Una ruta de combo ejecuta únicamente la secuencia elegida. Las
              continuaciones se registran como «route».
            </p>
          </>
        ) : tab === "timeline" ? (
          <div className="event-list">
            {events
              .filter((e) => !e.player_id || e.player_id === `p${player + 1}`)
              .slice(-30)
              .reverse()
              .map((e) => (
                <div key={e.seq}>
                  <span>#{e.seq}</span>
                  <b>{e.kind === "combat" ? e.event.kind : e.kind}</b>
                  <code>
                    {e.action ??
                      e.event?.move ??
                      e.reason ??
                      e.request_id?.slice(0, 8) ??
                      ""}
                  </code>
                  <small>{e.event?.source ?? ""}</small>
                </div>
              ))}
          </div>
        ) : (
          <pre>
            {JSON.stringify(
              tab === "input" ? p.last_request : p.last_result,
              null,
              2,
            )}
          </pre>
        )}
      </div>
      {p.error && <p className="error-banner">{p.error}</p>}
    </section>
  );
}
