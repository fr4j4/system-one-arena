import { useEffect, useRef, useState } from "react";
import Scene from "./Scene";
import { Hud } from "./Hud";
import {
  api,
  type Catalog,
  type Frame,
  type Match,
  type Settings,
} from "./types";
import type { CombatAudio } from "./audio";
const noop = () => {};
export function Replay({
  catalog,
  settings,
  audio,
  onError,
}: {
  catalog: Catalog;
  settings: Settings;
  audio: CombatAudio;
  onError: (s: string) => void;
}) {
  const [matches, setMatches] = useState<Match[]>([]),
    [selected, setSelected] = useState<Match | null>(null),
    [frames, setFrames] = useState<Frame[]>([]),
    [times, setTimes] = useState<number[]>([]),
    [index, setIndex] = useState(0),
    [playing, setPlaying] = useState(false),
    [speed, setSpeed] = useState(1),
    [loading, setLoading] = useState(false);
  const frameRef = useRef<Frame | null>(null),
    revision = useRef(0);
  useEffect(() => {
    api<Match[]>("/matches")
      .then(setMatches)
      .catch((e) => onError(String(e)));
    return () => {
      revision.current++;
    };
  }, [onError]);
  useEffect(() => {
    frameRef.current = frames[index]
      ? { ...frames[index], paused: !playing }
      : null;
  }, [frames, index, playing]);
  useEffect(() => {
    if (!playing || !frames.length) return;
    let raf = 0;
    const start = performance.now(),
      first = times[index];
    let position = index;
    const step = (now: number) => {
      const tick = first + ((now - start) / 1000) * speed;
      while (position + 1 < frames.length && times[position + 1] <= tick)
        position++;
      setIndex(position);
      if (position === frames.length - 1) setPlaying(false);
      else raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [playing, frames, speed, times]);
  const load = async (m: Match) => {
    const rev = ++revision.current;
    setLoading(true);
    setPlaying(false);
    try {
      let after = 0;
      const result: any[] = [];
      for (;;) {
        const page = await api<any[]>(
          `/matches/${m.id}/events?after=${after}&limit=5000`,
        );
        if (!page.length) break;
        result.push(...page);
        after = page.at(-1).seq;
      }
      if (rev !== revision.current) return;
      const snapshots = result
        .filter((e) => e.kind === "snapshot")
        .map((e) => e.state);
      setSelected(m);
      setFrames(snapshots);
      setTimes(result.filter((e) => e.kind === "snapshot").map((e) => e.at));
      setIndex(0);
      frameRef.current = snapshots[0] ?? m.state;
    } catch (e) {
      onError(String(e));
    } finally {
      if (rev === revision.current) setLoading(false);
    }
  };
  return (
    <section className="replay-page">
      <div className="section-heading">
        <div>
          <span className="eyebrow">MEMORIA DE LA ARENA</span>
          <h1>Cada combate deja una huella.</h1>
        </div>
        <span className="muted">Las repeticiones no consultan modelos.</span>
      </div>
      <div className="replay-layout">
        <aside className="replay-list">
          {matches.length === 0 ? (
            <p className="muted">Tus primeras partidas aparecerán aquí.</p>
          ) : (
            matches.map((m) => (
              <button
                className={m.id === selected?.id ? "selected" : ""}
                key={m.id}
                onClick={() => load(m)}
              >
                <small>{new Date(m.created_at).toLocaleString("es")}</small>
                <b>{m.config.players.map((p) => p.fighter_id).join(" / ")}</b>
                <span>
                  {m.config.players
                    .map((p) =>
                      p.controller === "human" ? "Tú" : p.model_profile_id,
                    )
                    .join(" vs ")}
                </span>
                <em>
                  {m.status} · {m.state?.wins.join(" — ") ?? "—"}
                </em>
              </button>
            ))
          )}
        </aside>
        <div className="replay-view">
          {loading ? (
            <div className="empty-state">Cargando los eventos grabados…</div>
          ) : selected && frames.length ? (
            <>
              <div className="arena-stage replay-stage">
                <Scene
                  frameRef={frameRef}
                  characters={selected.config.players.map((p) => p.fighter_id)}
                  arena={selected.config.arena_id}
                  settings={settings}
                  audio={audio}
                  onReady={noop}
                  onError={onError}
                />
                <Hud
                  frame={frames[index]}
                  catalog={catalog}
                  match={{ ...selected, status: "replay" }}
                  input={noop}
                />
              </div>
              <div className="replay-controls">
                <button
                  className="primary"
                  onClick={() => {
                    if (index === frames.length - 1) setIndex(0);
                    void audio.unlock();
                    setPlaying(!playing);
                  }}
                >
                  {playing ? "Pausar" : "Reproducir"}
                </button>
                <button
                  onClick={() => {
                    setPlaying(false);
                    setIndex((i) => Math.max(0, i - 1));
                  }}
                  aria-label="Frame anterior"
                >
                  ←
                </button>
                <button
                  onClick={() => {
                    setPlaying(false);
                    setIndex((i) => Math.min(frames.length - 1, i + 1));
                  }}
                  aria-label="Frame siguiente"
                >
                  →
                </button>
                <input
                  aria-label="Posición del replay"
                  type="range"
                  min="0"
                  max={frames.length - 1}
                  value={index}
                  onChange={(e) => {
                    setPlaying(false);
                    setIndex(+e.target.value);
                  }}
                />
                <select
                  aria-label="Velocidad del replay"
                  value={speed}
                  onChange={(e) => setSpeed(+e.target.value)}
                >
                  {[0.25, 0.5, 1, 2].map((v) => (
                    <option key={v} value={v}>
                      {v}×
                    </option>
                  ))}
                </select>
                <a href={`/api/v2/matches/${selected.id}/export`}>Exportar</a>
              </div>
              <div className="replay-markers">
                {frames.map((f, i) =>
                  (i === 0 || frames[i - 1].phase !== f.phase) &&
                  [
                    "clash",
                    "finish",
                    "finisher",
                    "round_over",
                    "cinematic",
                  ].includes(f.phase) ? (
                    <button
                      key={i}
                      onClick={() => {
                        setPlaying(false);
                        setIndex(i);
                      }}
                    >
                      {f.phase} · R{f.round}
                    </button>
                  ) : null,
                )}
              </div>
            </>
          ) : (
            <div className="empty-state">
              <span>◌</span>
              <h2>Vuelve al instante decisivo.</h2>
              <p>
                Selecciona un encuentro para explorar sus movimientos y
                decisiones.
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
