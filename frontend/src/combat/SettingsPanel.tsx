import { useEffect, useRef } from "react";
import type { Catalog, Profile, Settings } from "./types";
import { DEFAULT_KEYS, DEFAULT_GAMEPAD } from "./types";
export function SettingsPanel({
  value,
  onChange,
  onClose,
  profiles,
  catalog,
}: {
  value: Settings;
  onChange: (s: Settings) => void;
  onClose: () => void;
  profiles: Profile[];
  catalog: Catalog;
}) {
  const panel = useRef<HTMLElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const prior = document.activeElement as HTMLElement;
    panel.current?.querySelector<HTMLButtonElement>("button")?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.code === "Escape") {
        e.preventDefault();
        close.current();
      }
      if (e.code === "Tab") {
        const all = [
          ...panel.current!.querySelectorAll<HTMLElement>(
            'button,select,input,[tabindex="0"]',
          ),
        ];
        const first = all[0],
          last = all.at(-1);
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("keydown", key);
      prior?.focus();
    };
  }, []);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <section
        ref={panel}
        className="settings-panel"
        role="dialog"
        aria-modal="true"
        aria-label="Ajustes de la arena"
      >
        <header>
          <div>
            <small className="eyebrow">TU EXPERIENCIA</small>
            <h2>Ajustes de la arena</h2>
          </div>
          <button onClick={onClose} aria-label="Cerrar ajustes">
            ✕
          </button>
        </header>
        <div className="settings-scroll">
          <h3>Imagen y accesibilidad</h3>
          <label>
            Calidad gráfica
            <select
              value={value.quality}
              onChange={(e) =>
                onChange({
                  ...value,
                  quality: e.target.value as Settings["quality"],
                })
              }
            >
              <option value="high">Alta</option>
              <option value="medium">Media</option>
              <option value="low">Baja</option>
            </select>
          </label>
          {[
            ["reducedMotion", "Reducir movimiento"],
            ["reducedFlash", "Reducir destellos"],
            ["shake", "Sacudida de cámara"],
          ].map(([key, label]) => (
            <label className="toggle" key={key}>
              <span>{label}</span>
              <input
                type="checkbox"
                checked={!!value[key as keyof Settings]}
                onChange={(e) =>
                  onChange({ ...value, [key]: e.target.checked })
                }
              />
            </label>
          ))}
          <h3>Sonido</h3>
          {[
            ["master", "Volumen general"],
            ["music", "Música"],
            ["effects", "Efectos"],
          ].map(([key, label]) => (
            <label key={key}>
              {label}
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={Number(value[key as keyof Settings])}
                onChange={(e) => onChange({ ...value, [key]: +e.target.value })}
              />
            </label>
          ))}
          <h3>
            Teclado{" "}
            <button
              className="text-button"
              onClick={() =>
                onChange({ ...value, bindings: { ...DEFAULT_KEYS } })
              }
            >
              Restaurar
            </button>
          </h3>
          <p className="muted">
            Selecciona una tecla y pulsa su reemplazo. Escape pausa; S + L
            activa guardia baja. J/K/O/A deciden durante un choque.
          </p>
          <div className="key-grid">
            {Object.entries(value.bindings).map(([key, action]) => (
              <button
                key={key}
                onKeyDown={(e) => {
                  if (e.code === "Tab") return;
                  e.preventDefault();
                  e.stopPropagation();
                  const bindings = { ...value.bindings };
                  delete bindings[key];
                  bindings[e.code] = action;
                  onChange({ ...value, bindings });
                }}
              >
                <span>{catalog.actions[action] ?? action}</span>
                <kbd>
                  {key
                    .replace("Key", "")
                    .replace("Digit", "")
                    .replace("Left", "")}
                </kbd>
              </button>
            ))}
          </div>
          <h3>
            Mando{" "}
            <button
              className="text-button"
              onClick={() =>
                onChange({ ...value, gamepad: { ...DEFAULT_GAMEPAD } })
              }
            >
              Restaurar
            </button>
          </h3>
          <p className="muted">
            Stick izquierdo: movimiento. Asigna los botones según tu mando. L3
            activa la definitiva; R3 ejecuta el combo de poder. Mapeo estándar
            del navegador.
          </p>
          <div className="pad-grid">
            {Object.entries(value.gamepad).map(([id, action]) => (
              <label key={id}>
                Botón {id}
                <select
                  aria-label={"Mando botón " + id}
                  value={action}
                  onChange={(e) =>
                    onChange({
                      ...value,
                      gamepad: { ...value.gamepad, [id]: e.target.value },
                    })
                  }
                >
                  {Object.entries({ ...catalog.actions, pause: "Pausar" }).map(
                    ([key, name]) => (
                      <option key={key} value={key}>
                        {name}
                      </option>
                    ),
                  )}
                </select>
              </label>
            ))}
          </div>
          <h3>Perfiles de modelos</h3>
          <p className="muted">
            Las claves se configuran en el .env del servidor. Para añadir
            modelos del mismo proveedor, copia providers.example.json a
            providers.local.json y reinicia el backend.
          </p>
          {profiles.map((p) => (
            <div className="profile-row" key={p.id}>
              <span>
                <b>{p.name}</b>
                <small>{p.model || "Control de referencia"}</small>
              </span>
              <em className={p.configured ? "online" : ""}>
                {p.configured ? "Disponible" : "Sin configurar"}
              </em>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
