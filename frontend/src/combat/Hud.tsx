import type { Catalog, Frame, Match } from "./types";
export function Hud({
  frame,
  catalog,
  match,
  input,
}: {
  frame: Frame | null;
  catalog: Catalog;
  match: Match | null;
  input: (a: string) => void;
}) {
  if (!frame) return null;
  const active = match?.status === "running";
  const human =
    match?.config.players.findIndex((p) => p.controller === "human") ?? -1;
  const winner = frame.fighters.find((f) => f.id === frame.winner);
  const character = catalog.fighters.find((c) => c.id === winner?.character);
  return (
    <>
      <div className="fight-hud-v2">
        {frame.fighters.map((f, i) => {
          const c = catalog.fighters.find((c) => c.id === f.character)!;
          return (
            <div
              key={f.id}
              className={"health-slot side-" + i}
              style={{ "--fighter": c.color } as React.CSSProperties}
            >
              <div className="health-name">
                <small>PLAYER {i + 1}</small>
                <strong>{c.name}</strong>
                <b>
                  {Math.ceil(f.health)}
                  <span> / 1000</span>
                </b>
              </div>
              <div className="health-track">
                <i style={{ width: `${f.health / 10}%` }} />
              </div>
              <div className="resource-line">
                <span className="energy-track">
                  <i style={{ width: f.energy + "%" }} />
                </span>
                <b>
                  {Math.floor(f.energy)}
                  <small> EN</small>
                </b>
              </div>
              <div className="resource-line guard-line">
                <span className="guard-track">
                  <i style={{ width: f.guard + "%" }} />
                </span>
                <b>
                  {Math.ceil(f.guard)}
                  <small> GD</small>
                </b>
              </div>
              <div className="fighter-caption">
                <span>
                  {f.energy >= 100
                    ? "DEFINITIVA LISTA"
                    : (catalog.actions[f.action] ?? f.action)}
                </span>
                <span className="round-pips">
                  {Array.from(
                    { length: Math.floor(frame.best_of / 2) + 1 },
                    (_, n) => (
                      <i key={n} className={n < frame.wins[i] ? "won" : ""} />
                    ),
                  )}
                </span>
              </div>
              {f.combo_hits > 1 && (
                <div className="combo-count">
                  <b>{f.combo_hits}</b> HITS
                </div>
              )}
            </div>
          );
        })}
        <div className="round-clock">
          <b>{Math.ceil(frame.timer)}</b>
          <span>RONDA {frame.round}</span>
        </div>
      </div>
      {!match && (
        <div className="preview-wordmark">
          <span>ELIGE TU LUCHADOR</span>
          <strong>
            Un encuentro.
            <br />
            <em>Infinitas decisiones.</em>
          </strong>
        </div>
      )}
      {match?.status === "preparing" && (
        <div className="phase-overlay">
          <small>CONEXIÓN DE JUGADORES</small>
          <strong>Preparando modelos</strong>
          <p>La arena comenzará cuando ambos estén listos.</p>
        </div>
      )}
      {match?.status === "paused" && (
        <div className="phase-overlay">
          <small>SIMULACIÓN Y CONSULTAS PAUSADAS</small>
          <strong>Pausa</strong>
        </div>
      )}
      {active && frame.phase === "intro" && (
        <div className="phase-overlay intro">
          <small>RONDA {frame.round}</small>
          <strong>PREPÁRATE</strong>
        </div>
      )}
      {active && frame.phase === "round_over" && (
        <div className="phase-overlay">
          <small>
            {frame.rounds.at(-1)?.winner?.toUpperCase() ?? "EMPATE"}
          </small>
          <strong>
            {frame.rounds.at(-1)?.reason === "KO" ? "K.O." : "TIEMPO"}
          </strong>
        </div>
      )}
      {active && frame.phase === "clash" && (
        <div className="clash-overlay">
          <small>VOLUNTADES EN COLISIÓN</small>
          <h2>CHOQUE DE ENERGÍA</h2>
          <div className="clash-score">
            <b>{frame.clash.score[0]}</b>
            <span>PULSO {frame.clash.pulse} / 3</span>
            <b>{frame.clash.score[1]}</b>
          </div>
          <progress max="48" value={frame.clash.left} />
          {frame.clash.history.map((h: any) => (
            <div className="clash-reveal" key={h.pulse}>
              <span>Pulso {h.pulse}</span>
              {h.choices.map((c: any, i: number) => (
                <b key={i}>
                  P{i + 1}: {catalog.actions[c.action] ?? c.action}
                  {c.source === "fallback" ? " (sin respuesta)" : ""}
                </b>
              ))}
            </div>
          ))}
          {human >= 0 ? (
            <div className="clash-choices">
              {[
                ["hold", "Sostener", 0],
                ["push", "Impulsar", 10],
                ["surge", "Sobrecargar", 20],
                ["yield", "Ceder", 0],
              ].map(([id, label, cost]) => (
                <button
                  key={id}
                  disabled={frame.fighters[human].energy < Number(cost)}
                  onClick={() => input(String(id))}
                >
                  {label}
                  <small>{cost} EN</small>
                </button>
              ))}
            </div>
          ) : (
            <p>
              Las elecciones de ambos modelos se revelan al cerrar cada pulso.
            </p>
          )}
        </div>
      )}
      {active && frame.phase === "finish" && (
        <div className="phase-overlay finisher-prompt">
          <small>{winner?.name} GANA</small>
          <strong>UN ÚLTIMO DESTELLO</strong>
          {human >= 0 && winner?.id === `p${human + 1}` ? (
            <div>
              <button className="primary" onClick={() => input("finish")}>
                {character?.finisher}
              </button>
              <button onClick={() => input("spare")}>Perdonar</button>
            </div>
          ) : (
            <p>El vencedor decide cómo termina esta historia.</p>
          )}
        </div>
      )}
      {active && frame.phase === "finisher" && (
        <div className="cinematic-title">
          <small>TÉCNICA FINAL · {winner?.name}</small>
          <strong>{character?.finisher}</strong>
        </div>
      )}
      {active && frame.phase === "cinematic" && (
        <div className="cinematic-title">
          <small>ENERGÍA LIBERADA</small>
          <strong>
            {
              catalog.fighters.find(
                (c) =>
                  c.id ===
                  frame.fighters.find(
                    (f) => f.id === frame.cinematic?.player_id,
                  )?.character,
              )?.ultimate
            }
          </strong>
        </div>
      )}
      {match && ["completed", "stopped", "failed"].includes(match.status) && (
        <div className="result-overlay">
          <small>
            {match.status === "stopped"
              ? "COMBATE DETENIDO"
              : match.status === "failed"
                ? "PARTIDA INTERRUMPIDA"
                : "FIN DEL COMBATE"}
          </small>
          <strong>
            {match.status === "completed"
              ? winner
                ? `${winner.name} GANA`
                : frame.done
                  ? "EMPATE"
                  : "LÍMITE DE TIEMPO"
              : "La arena espera"}
          </strong>
          <p>
            {frame.wins[0]} — {frame.wins[1]} <span>RONDAS</span>
          </p>
        </div>
      )}
      <div className="stage-caption">
        <span>{catalog.arenas.find((a) => a.id === frame.arena)?.name}</span>
        <span>
          {match?.status === "replay"
            ? "REPLAY · SIN CONSULTAS"
            : match
              ? "ENCUENTRO EN VIVO"
              : "VISTA PREVIA · SIN CONSULTAS"}
        </span>
      </div>
    </>
  );
}
