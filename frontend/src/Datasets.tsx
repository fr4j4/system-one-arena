import { useEffect, useState } from "react";
import { Download, FileUp, Save } from "lucide-react";
import { api, download, post, type Scenario } from "./types";
export default function Datasets({
  scenarios,
  onDataset,
  onError,
}: {
  scenarios: Scenario[];
  onDataset: (name: string, items: any[]) => void;
  onError: (s: string) => void;
}) {
  const [name, setName] = useState("tickets"),
    [text, setText] = useState(""),
    [notice, setNotice] = useState(""),
    [saved, setSaved] = useState<any[]>([]);
  useEffect(() => {
    api<any[]>("/presets")
      .then((v) => setSaved(v.filter((p) => p.kind === "dataset")))
      .catch((e) => onError(String(e)));
  }, []);
  useEffect(() => {
    api<any[]>("/fixtures/" + name)
      .then((items) => setText(items.map((i) => JSON.stringify(i)).join("\n")))
      .catch((e) => onError(String(e)));
  }, [name]);
  const parse = () => {
    const items = text
      .trim()
      .split("\n")
      .filter(Boolean)
      .map((l) => JSON.parse(l));
    if (
      !items.length ||
      items.some((i) => !i.state || typeof i.state !== "object")
    )
      throw new Error(
        "Cada línea requiere un objeto con state y, opcionalmente, expected.",
      );
    return items;
  };
  const save = async () => {
    try {
      const items = parse();
      await post("/presets", {
        id: "dataset-" + Date.now(),
        name: name + " · " + items.length + " casos",
        kind: "dataset",
        value: items,
      });
      onDataset(name, items);
      setNotice("Dataset guardado y seleccionado para Arena.");
      setSaved(
        (await api<any[]>("/presets")).filter((p) => p.kind === "dataset"),
      );
    } catch (e) {
      onError(String(e));
    }
  };
  return (
    <section className="workspace-page">
      <div className="section-heading">
        <div>
          <span className="eyebrow">ENTRADAS REPRODUCIBLES</span>
          <h2>El mismo problema. Distintos modelos.</h2>
          <p>
            Los datos de entrada se envían al modelo. Las etiquetas esperadas
            permanecen en el evaluador.
          </p>
        </div>
        <button className="primary" onClick={save}>
          <Save size={16} /> Guardar y usar
        </button>
      </div>
      <div className="toolbar">
        <label>
          Escenario
          <select value={name} onChange={(e) => setName(e.target.value)}>
            {scenarios
              .filter((s) => s.kind === "business")
              .map((s) => (
                <option value={s.id} key={s.id}>
                  {s.name}
                </option>
              ))}
          </select>
        </label>
        <label className="file-button">
          <FileUp size={16} /> Importar JSONL
          <input
            type="file"
            accept=".jsonl,.json"
            onChange={async (e) => {
              const f = e.target.files?.[0];
              if (f) {
                if (f.size > 10_000_000) {
                  onError("El archivo supera 10 MB");
                  return;
                }
                const str = await f.text();
                try {
                  const parsed = JSON.parse(str);
                  setText(
                    Array.isArray(parsed)
                      ? parsed.map((v) => JSON.stringify(v)).join("\n")
                      : str,
                  );
                } catch {
                  setText(str);
                }
              }
            }}
          />
        </label>
        <button
          onClick={() => {
            try {
              download(
                name + ".jsonl",
                parse()
                  .map((i) => JSON.stringify(i))
                  .join("\n"),
              );
            } catch (e) {
              onError(String(e));
            }
          }}
        >
          <Download size={15} /> Exportar
        </button>
        {saved.length ? (
          <label>
            Guardados
            <select
              value=""
              onChange={(e) => {
                const p = saved.find((p) => p.id === e.target.value);
                if (p)
                  setText(
                    p.value.map((v: any) => JSON.stringify(v)).join("\n"),
                  );
              }}
            >
              <option value="">Seleccionar…</option>
              {saved.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </div>
      {notice ? <p className="notice">{notice}</p> : null}
      <div className="dataset-layout">
        <div>
          <div className="editor-caption">
            <b>DATASET / JSONL</b>
            <span>Un caso por línea</span>
          </div>
          <textarea
            className="dataset-editor"
            spellCheck={false}
            aria-label="Editor JSONL"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </div>
        <aside className="explanation">
          <h3>Etiqueta lo que sabes.</h3>
          <p>
            <code>state</code> contiene el texto o los hechos.{" "}
            <code>expected</code> contiene las respuestas correctas por
            pregunta.
          </p>
          <pre>
            {
              '{"id":"caso-1",\n "state":{"text":"..."},\n "expected":{\n   "department":"billing",\n   "priority":[0,1]\n }}'
            }
          </pre>
          <p>
            Un arreglo de etiquetas expresa ambigüedad: cualquiera de esas
            respuestas es aceptable. Esos casos no se usan para calibración de
            una única etiqueta.
          </p>
          <div className="info-note">
            Los fixtures incluidos son sintéticos y pequeños. Sirven para
            verificar el flujo, no para afirmar precisión de producción.
          </div>
        </aside>
      </div>
    </section>
  );
}
