import { useCallback, useEffect, useRef, useState } from "react";
import {
  Settings2,
  Play,
  Pause,
  Square,
  ChevronDown,
  RotateCcw,
} from "lucide-react";
import Scene from "./combat/Scene";
import { Hud } from "./combat/Hud";
import { Inspector } from "./combat/Inspector";
import { SettingsPanel } from "./combat/SettingsPanel";
import { Laboratory } from "./combat/Laboratory";
import { Replay } from "./combat/Replay";
import { CombatAudio } from "./combat/audio";
import { useMatch } from "./combat/useMatch";
import { useControls } from "./combat/useControls";
import {
  api,
  DEFAULT_CONFIG,
  DEFAULT_KEYS,
  DEFAULT_GAMEPAD,
  type Catalog,
  type Config,
  type Match,
  type Profile,
  type Settings,
} from "./combat/types";
const initialSettings = (): Settings => {
  const defaults: Settings = {
    quality: "high",
    reducedMotion: matchMedia("(prefers-reduced-motion: reduce)").matches,
    reducedFlash: false,
    shake: true,
    master: 0.5,
    music: 0.16,
    effects: 0.7,
    bindings: { ...DEFAULT_KEYS },
    gamepad: { ...DEFAULT_GAMEPAD },
  };
  try {
    return {
      ...defaults,
      ...JSON.parse(localStorage.getItem("eclipse-settings-v2") ?? "{}"),
    };
  } catch {
    return defaults;
  }
};
export default function App() {
  const [catalog, setCatalog] = useState<Catalog | null>(null),
    [profiles, setProfiles] = useState<Profile[]>([]),
    [config, setConfig] = useState<Config>(DEFAULT_CONFIG),
    [tab, setTab] = useState("arena"),
    [settings, setSettings] = useState(initialSettings),
    [showSettings, setShowSettings] = useState(false),
    [ready, setReady] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [inspector, setInspector] = useState(true);
  const onError = useCallback(
    (s: string) => setError(s.replace(/^Error: /, "")),
    [],
  );
  const game = useMatch(onError);
  const live = useRef(game);
  live.current = game;
  const [audio] = useState(() => new CombatAudio(settings));
  const active =
    !!game.match &&
    ["preparing", "running", "paused"].includes(game.match.status);
  const human = config.players.some((p) => p.controller === "human");
  const rendererError = useCallback(
    (s: string) => {
      onError(s);
      if (live.current.match?.status === "running")
        void live.current.command("pause");
    },
    [onError],
  );
  useControls(
    game.match?.status === "running" && !showSettings,
    settings,
    game.input,
    game.frameRef,
    () => void game.command("pause"),
  );
  useEffect(() => {
    audio.configure(settings);
    localStorage.setItem("eclipse-settings-v2", JSON.stringify(settings));
  }, [audio, settings]);
  useEffect(() => {
    let alive = true;
    Promise.all([
      api<Catalog>("/catalog"),
      api<Profile[]>("/profiles"),
      api<Match[]>("/matches"),
    ])
      .then(([c, p, m]) => {
        if (!alive) return;
        setCatalog(c);
        setProfiles(p);
        const running = m.find((x) =>
          ["preparing", "running", "paused"].includes(x.status),
        );
        if (running) {
          setConfig(running.config);
          live.current.attach(running);
        }
      })
      .catch((e) => onError(String(e)));
    return () => {
      alive = false;
    };
  }, [onError]);
  useEffect(() => {
    if (game.match) return;
    let alive = true;
    api("/preview", config)
      .then((s) => {
        if (alive) game.preview(s);
      })
      .catch((e) => onError(String(e)));
    return () => {
      alive = false;
    };
  }, [config, game.match, game.preview, onError]);
  useEffect(() => {
    if (game.match?.status === "running") audio.startMusic();
    else audio.stopMusic();
    return () => audio.stopMusic();
  }, [audio, game.match?.status]);
  const change = (next: Config) => {
    if (active) return;
    game.clear();
    setConfig(next);
  };
  const start = async () => {
    setBusy(true);
    setError("");
    try {
      await audio.unlock();
      const m = await api<Match>("/matches", config);
      game.attach(m);
    } catch (e) {
      onError(String(e));
    } finally {
      setBusy(false);
    }
  };
  const mode = (value: string) => {
    const next = structuredClone(config);
    next.mode = value === "training" ? "training" : "duel";
    if (value === "human" || value === "training") {
      next.players[0].controller = "human";
      if (next.players[1].controller === "human")
        next.players[1] = {
          ...next.players[1],
          controller: "baseline",
          model_profile_id: "reference",
        };
      if (value === "training")
        next.players[1] = {
          ...next.players[1],
          controller: "baseline",
          model_profile_id: "dummy",
        };
    } else
      next.players = next.players.map((p) =>
        p.controller === "human"
          ? { ...p, controller: "baseline", model_profile_id: "reference" }
          : p,
      );
    change(next);
  };
  const configured = config.players.every(
    (p) =>
      p.controller === "human" ||
      profiles.find((m) => m.id === p.model_profile_id)?.configured,
  );
  if (!catalog)
    return (
      <main className="boot-screen">
        <span className="brand-symbol">◒</span>
        <h1>ECLIPSE ARENA</h1>
        <p>{error || "Conectando con la arena…"}</p>
        {error && <button onClick={() => location.reload()}>Reintentar</button>}
      </main>
    );
  return (
    <>
      <header className="app-header">
        <a
          href="#"
          className="brand"
          onClick={(e) => {
            e.preventDefault();
            setTab("arena");
          }}
        >
          <span className="brand-symbol">◒</span>
          <span>
            ECLIPSE <b>ARENA</b>
            <small>SYSTEM ONE / COMBAT LAB</small>
          </span>
        </a>
        <nav aria-label="Navegación principal">
          {[
            ["arena", "Arena"],
            ["lab", "Laboratorio"],
            ["replays", "Replays"],
          ].map(([id, label]) => (
            <button
              key={id}
              className={tab === id ? "selected" : ""}
              onClick={() => {
                if (human && active && id === "replays")
                  void game.command("pause");
                setTab(id);
              }}
            >
              {label}
            </button>
          ))}
        </nav>
        <div className="header-tools">
          {active && tab === "replays" && (
            <button
              className="stop-button"
              onClick={() => void game.command("stop")}
            >
              Detener partida activa
            </button>
          )}
          <span className="connection">
            <i />
            {active ? "PARTIDA ACTIVA" : "ARENA DISPONIBLE"}
          </span>
          <button
            className="icon-button"
            aria-label="Ajustes"
            onClick={() => {
              if (human && active) void game.command("pause");
              setShowSettings(true);
            }}
          >
            <Settings2 size={19} />
          </button>
        </div>
      </header>
      {error && (
        <div className="error-banner global-error" role="alert">
          <span>{error}</span>
          <button onClick={() => setError("")} aria-label="Cerrar error">
            ✕
          </button>
        </div>
      )}
      <main className="main-shell">
        {tab === "replays" ? (
          <Replay
            catalog={catalog}
            settings={settings}
            audio={audio}
            onError={onError}
          />
        ) : (
          <>
            <div className="page-intro">
              <div>
                <span className="eyebrow">INTELIGENCIA BAJO PRESIÓN</span>
                <h1>
                  La próxima decisión
                  <br className="mobile-break" /> cambia el combate.
                </h1>
              </div>
              <div className="mode-switch segmented">
                {[
                  ["models", "Modelo vs modelo"],
                  ["human", "Jugar"],
                  ["training", "Entrenar"],
                ].map(([id, label]) => (
                  <button
                    key={id}
                    disabled={active}
                    className={
                      (config.mode === "training"
                        ? "training"
                        : human
                          ? "human"
                          : "models") === id
                        ? "selected"
                        : ""
                    }
                    onClick={() => mode(id)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <section
              className="versus-setup"
              aria-label="Seleccionar jugadores"
            >
              {config.players.map((slot, i) => (
                <div
                  className={"player-select player-" + i}
                  key={i}
                  style={
                    {
                      "--fighter": catalog.fighters.find(
                        (c) => c.id === slot.fighter_id,
                      )?.color,
                    } as React.CSSProperties
                  }
                >
                  <div className="slot-heading">
                    <span>PLAYER 0{i + 1}</span>
                    <b>
                      {
                        catalog.fighters.find((c) => c.id === slot.fighter_id)
                          ?.title
                      }
                    </b>
                  </div>
                  <div className="fighter-picker">
                    {catalog.fighters.map((c) => (
                      <button
                        disabled={active}
                        key={c.id}
                        aria-label={`P${i + 1} ${c.name}`}
                        aria-pressed={slot.fighter_id === c.id}
                        className={slot.fighter_id === c.id ? "selected" : ""}
                        style={{ "--color": c.color } as React.CSSProperties}
                        onClick={() =>
                          change({
                            ...config,
                            players: config.players.map((p, n) =>
                              n === i ? { ...p, fighter_id: c.id } : p,
                            ),
                          })
                        }
                      >
                        <span className={"fighter-emblem emblem-" + c.id}>
                          {
                            { ember: "焔", flux: "ϟ", terra: "◆", nyx: "☾" }[
                              c.id
                            ]
                          }
                        </span>
                        <span>
                          <strong>{c.name}</strong>
                          <small>{c.role}</small>
                        </span>
                      </button>
                    ))}
                  </div>
                  <label className="controller-select">
                    <span>CONTROLADOR</span>
                    <select
                      aria-label={`Controlador P${i + 1}`}
                      disabled={active}
                      value={
                        slot.controller === "human"
                          ? "human"
                          : slot.model_profile_id
                      }
                      onChange={(e) => {
                        const id = e.target.value;
                        change({
                          ...config,
                          players: config.players.map((p, n) =>
                            n === i
                              ? {
                                  ...p,
                                  controller:
                                    id === "human"
                                      ? "human"
                                      : profiles.find((x) => x.id === id)?.ai
                                        ? "model"
                                        : "baseline",
                                  model_profile_id:
                                    id === "human" ? "reference" : id,
                                }
                              : p,
                          ),
                        });
                      }}
                    >
                      <option
                        value="human"
                        disabled={config.players.some(
                          (p, n) => n !== i && p.controller === "human",
                        )}
                      >
                        Tú · teclado / mando
                      </option>
                      {profiles.map((p) => (
                        <option
                          key={p.id}
                          value={p.id}
                          disabled={!p.configured}
                        >
                          {p.name}

                          {!p.configured ? " · sin configurar" : ""}
                        </option>
                      ))}
                    </select>
                  </label>
                  {game.match && (
                    <div className="decision-state" aria-live="polite">
                      <span
                        className={
                          game.match.status === "running" &&
                          game.match.players[i].pending
                            ? "thinking"
                            : ""
                        }
                      />
                      {slot.controller === "human"
                        ? "Control humano"
                        : game.match.players[i].error
                          ? "Error del proveedor"
                          : game.match.status === "running" &&
                              game.match.players[i].pending
                            ? "Procesando decisión…"
                            : game.match.players[i].last_result?.answers?.action
                                  ?.value
                              ? `Última elección: ${catalog.actions[game.match.players[i].last_result.answers.action.value] ?? game.match.players[i].last_result.answers.action.value}`
                              : "Esperando decisión"}
                      <em>
                        {game.match.players[i].latency.p50?.toFixed(0) ?? "—"}{" "}
                        ms p50
                      </em>
                    </div>
                  )}
                </div>
              ))}
              <div className="versus-seal">VS</div>
            </section>
            <section className="arena-stage">
              <Scene
                frameRef={game.frameRef}
                characters={config.players.map((p) => p.fighter_id)}
                arena={config.arena_id}
                settings={settings}
                audio={audio}
                onReady={setReady}
                onError={rendererError}
              />
              <Hud
                frame={game.frame}
                catalog={catalog}
                match={game.match}
                input={game.input}
              />
            </section>
            <section className="match-controls">
              <div className="match-options">
                <label>
                  ESCENARIO
                  <select
                    disabled={active}
                    value={config.arena_id}
                    onChange={(e) =>
                      change({ ...config, arena_id: e.target.value })
                    }
                  >
                    {catalog.arenas.map((a) => (
                      <option value={a.id} key={a.id}>
                        {a.name}
                      </option>
                    ))}
                  </select>
                </label>
                {config.mode === "duel" ? (
                  <>
                    <label>
                      FORMATO
                      <select
                        disabled={active}
                        value={config.best_of}
                        onChange={(e) =>
                          change({
                            ...config,
                            best_of: +e.target.value as 1 | 3 | 5,
                          })
                        }
                      >
                        {[1, 3, 5].map((n) => (
                          <option key={n} value={n}>
                            Mejor de {n}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      RONDA
                      <select
                        disabled={active}
                        value={config.round_seconds}
                        onChange={(e) =>
                          change({ ...config, round_seconds: +e.target.value })
                        }
                      >
                        {[30, 60, 90, 120].map((n) => (
                          <option key={n} value={n}>
                            {n} segundos
                          </option>
                        ))}
                      </select>
                    </label>
                  </>
                ) : (
                  <label>
                    EJERCICIO
                    <select
                      disabled={active}
                      value={config.preset}
                      onChange={(e) =>
                        change({ ...config, preset: e.target.value })
                      }
                    >
                      {Object.entries(catalog.presets).map(([id, name]) => (
                        <option key={id} value={id}>
                          {name}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
              </div>
              <div className="play-controls">
                {active ? (
                  <>
                    <button
                      disabled={game.match?.status === "preparing"}
                      onClick={() =>
                        void game.command(
                          game.match?.status === "paused" ? "resume" : "pause",
                        )
                      }
                    >
                      {game.match?.status === "paused" ? (
                        <Play size={16} />
                      ) : (
                        <Pause size={16} />
                      )}{" "}
                      {game.match?.status === "paused" ? "Reanudar" : "Pausar"}
                    </button>
                    <button
                      className="stop-button"
                      onClick={() => void game.command("stop")}
                    >
                      <Square size={14} /> Detener
                    </button>
                    {config.mode === "training" && (
                      <>
                        <button
                          title="Reiniciar ejercicio"
                          onClick={() => void game.command("reset")}
                        >
                          <RotateCcw size={16} />
                        </button>
                        {game.match?.status === "paused" && (
                          <button onClick={() => void game.command("step")}>
                            +1 frame
                          </button>
                        )}
                      </>
                    )}
                    {["finisher", "cinematic", "finish"].includes(
                      game.frame?.phase ?? "",
                    ) && (
                      <button onClick={() => void game.command("skip")}>
                        Omitir
                      </button>
                    )}
                  </>
                ) : (
                  <button
                    className="primary start-button"
                    disabled={!ready || busy || !configured}
                    onClick={start}
                  >
                    <Play size={17} fill="currentColor" />
                    {busy
                      ? "Preparando…"
                      : !ready
                        ? "Cargando arena…"
                        : game.match
                          ? "Revancha"
                          : "Iniciar combate"}
                  </button>
                )}
              </div>
            </section>
            <div className="arena-footnote">
              <span>
                <i className="live-dot" />
                {config.players.every((p) => p.controller !== "model")
                  ? "CONTROLADORES DE REFERENCIA · SIN CONSULTAS A IA"
                  : "DECISIONES REALES · UN CONTROLADOR POR JUGADOR"}
              </span>
              <button
                className="text-button"
                onClick={() => setInspector(!inspector)}
              >
                Inspector de decisiones <ChevronDown size={14} />
              </button>
            </div>
            {human && (
              <div className="human-help">
                <kbd>A</kbd>
                <kbd>D</kbd> mover <kbd>J</kbd> golpe <kbd>K</kbd> fuerte{" "}
                <kbd>L</kbd> bloquear <kbd>H</kbd> cargar <kbd>I</kbd> rayo{" "}
                <kbd>1–4</kbd> combos <kbd>Esc</kbd> pausa{" "}
                <button
                  className="text-button"
                  onClick={() => {
                    if (active) void game.command("pause");
                    setShowSettings(true);
                  }}
                >
                  Todos los controles
                </button>
              </div>
            )}
            {game.match && inspector && (
              <Inspector match={game.match} events={game.events} />
            )}
            {tab === "lab" && (
              <Laboratory
                config={config}
                onWatch={(m) => {
                  setConfig(m.config);
                  game.attach(m);
                }}
                onError={onError}
              />
            )}
            <details className="moves-guide">
              <summary>
                El arte del combate <span>Reglas, energía y técnicas</span>
              </summary>
              <div className="rules-grid">
                <article>
                  <span>01 / DOMINA EL RITMO</span>
                  <h3>Cada apertura cuenta.</h3>
                  <p>
                    Bloquea alto o bajo. Anticipa un golpe con parry. El agarre
                    vence a la guardia; el barrido vence a la guardia alta. Un
                    dash acerca, pero no te hace invulnerable.
                  </p>
                </article>
                <article>
                  <span>02 / ADMINISTRA TU ENERGÍA</span>
                  <h3>Acumula. Arriesga. Libera.</h3>
                  <p>
                    Empiezas con 25 EN. Carga para recuperar 12 por segundo.
                    Proyectil: 15. Técnica: 25. Rayo: 35. Definitiva: 100.
                    Romper un combo cuesta 50.
                  </p>
                </article>
                <article>
                  <span>03 / CHOQUE DE PODERES</span>
                  <h3>Dos voluntades, tres pulsos.</h3>
                  <p>
                    Los rayos que colisionan abren un duelo simultáneo. Sostén,
                    impulsa o sobrecarga. La elección rival permanece oculta
                    hasta resolver cada pulso. Repetir sobrecarga reduce su
                    fuerza.
                  </p>
                </article>
              </div>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Movimiento</th>
                      <th>Energía</th>
                      <th>Daño base</th>
                      <th>Preparación</th>
                      <th>Recuperación</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(catalog.moves).map(([id, m]) => (
                      <tr key={id}>
                        <td>{m.label}</td>
                        <td>{m.energy}</td>
                        <td>{m.damage}</td>
                        <td>{m.startup} frames</td>
                        <td>{m.recovery} frames</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          </>
        )}
      </main>
      <footer className="app-footer">
        <span>
          ECLIPSE ARENA <b>/</b> SYSTEM ONE
        </span>
        <span>
          Personajes originales · Combate 2.5D · {catalog.rules_version}
        </span>
      </footer>
      {showSettings && (
        <SettingsPanel
          value={settings}
          onChange={setSettings}
          onClose={() => setShowSettings(false)}
          profiles={profiles}
          catalog={catalog}
        />
      )}
    </>
  );
}
