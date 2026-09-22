import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  applyNodeChanges,
  type NodeChange,
  type Connection,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Plus, Save, Check } from "lucide-react";
import { api, post, type Graph, type GraphNode } from "./types";

function FlowNode({ data }: { data: any }) {
  const n: GraphNode = data.node;
  return (
    <div className={"flow-node " + n.kind}>
      <Handle type="target" position={Position.Top} />
      <small>
        {n.kind === "question"
          ? "PREGUNTA"
          : n.kind === "condition"
            ? "CONDICIÓN"
            : "SALIDA"}
      </small>
      <strong>{n.label ?? n.id}</strong>
      <span>
        {n.kind === "question"
          ? n.question?.type
          : n.kind === "condition"
            ? `${n.source} ${n.operator} ${n.value}`
            : "Acción simulada"}
      </span>
      {n.kind === "question" ? (
        <Handle type="source" position={Position.Bottom} />
      ) : n.kind === "condition" ? (
        <>
          <Handle
            id="yes"
            type="source"
            position={Position.Bottom}
            style={{ left: "30%", background: "#28aa91" }}
          />
          <Handle
            id="no"
            type="source"
            position={Position.Bottom}
            style={{ left: "70%", background: "#d99a42" }}
          />
          <div className="branch-labels">
            <b>Sí</b>
            <b>No</b>
          </div>
        </>
      ) : null}
    </div>
  );
}
const nodeTypes = { arena: FlowNode };
export default function WorkflowEditor({
  graph,
  onGraph,
  onError,
}: {
  graph: Graph | undefined;
  onGraph: (g: Graph) => void;
  onError: (s: string) => void;
}) {
  const [selected, setSelected] = useState<string>(""),
    [text, setText] = useState(""),
    [notice, setNotice] = useState(""),
    [saved, setSaved] = useState<any[]>([]);
  useEffect(() => {
    api<any[]>("/presets")
      .then((v) => setSaved(v.filter((p) => p.kind === "graph")))
      .catch((e) => onError(String(e)));
  }, []);
  const current = graph?.nodes.find((n) => n.id === selected);
  useEffect(() => {
    setText(current?.question ? JSON.stringify(current.question, null, 2) : "");
  }, [selected, graph?.start]);
  const nodes = useMemo(
    () =>
      graph?.nodes.map((node, i) => ({
        id: node.id,
        type: "arena",
        position: node.position ?? {
          x: node.kind === "output" ? (i % 2) * 240 : 120,
          y: i * 125,
        },
        data: { node },
        selected: node.id === selected,
      })) ?? [],
    [graph, selected],
  );
  const edges = useMemo(
    () =>
      graph?.nodes.flatMap<Edge>((n) =>
        n.kind === "question"
          ? [
              {
                id: n.id + "-next",
                source: n.id,
                target: n.next ?? "",
                animated: false,
              },
            ]
          : n.kind === "condition"
            ? [
                {
                  id: n.id + "-yes",
                  source: n.id,
                  sourceHandle: "yes",
                  target: n.yes ?? "",
                  label: "Sí",
                },
                {
                  id: n.id + "-no",
                  source: n.id,
                  sourceHandle: "no",
                  target: n.no ?? "",
                  label: "No",
                },
              ]
            : [],
      ) ?? [],
    [graph],
  );
  const update = (patch: Partial<GraphNode>) => {
    if (graph)
      onGraph({
        ...graph,
        nodes: graph.nodes.map((n) =>
          n.id === selected ? { ...n, ...patch } : n,
        ),
      });
  };
  const connect = useCallback(
    (c: Connection) => {
      if (!graph) return;
      onGraph({
        ...graph,
        nodes: graph.nodes.map((n) =>
          n.id === c.source
            ? {
                ...n,
                ...(n.kind === "condition"
                  ? { [c.sourceHandle === "yes" ? "yes" : "no"]: c.target }
                  : { next: c.target }),
              }
            : n,
        ),
      });
    },
    [graph],
  );
  const changeNodes = (changes: NodeChange[]) => {
    if (!graph) return;
    const moved = applyNodeChanges(changes, nodes);
    onGraph({
      ...graph,
      nodes: graph.nodes.map((n) => ({
        ...n,
        position: moved.find((m) => m.id === n.id)?.position ?? n.position,
      })),
    });
  };
  const load = async (template: string) => {
    try {
      const value = await api<Graph>("/graphs/" + template);
      onGraph(value);
      setSelected("");
      setNotice("Plantilla cargada");
    } catch (e) {
      onError(String(e));
    }
  };
  const validate = async (save = false) => {
    if (!graph) return;
    try {
      await post("/graphs/validate", graph);
      if (save) {
        await post("/presets", {
          id: "graph-" + Date.now(),
          kind: "graph",
          name: "Árbol " + new Date().toLocaleTimeString(),
          value: graph,
        });
        setSaved(
          (await api<any[]>("/presets")).filter((p) => p.kind === "graph"),
        );
      }
      setNotice(
        save
          ? "Árbol guardado"
          : "Árbol válido: sin ciclos ni dependencias rotas",
      );
    } catch (e) {
      onError(String(e));
    }
  };
  const add = (kind: GraphNode["kind"]) => {
    if (!graph) return;
    const id = kind + "-" + Date.now().toString(36);
    const node: GraphNode = {
      id,
      kind,
      position: { x: 380, y: 100 },
      ...(kind === "question"
        ? {
            question: {
              type: "boolean_probability",
              instructions: "Does this request need human review?",
            },
            next: graph.nodes.at(-1)?.id,
          }
        : kind === "condition"
          ? {
              source: graph.start,
              operator: "eq",
              value: "billing",
              yes: graph.nodes.at(-1)?.id,
              no: graph.nodes.at(-1)?.id,
            }
          : { label: "Nueva salida" }),
    };
    onGraph({ ...graph, nodes: [...graph.nodes, node] });
    setSelected(id);
  };
  return (
    <section className="workspace-page">
      <div className="section-heading">
        <div>
          <span className="eyebrow">DECISIONES COMPUESTAS</span>
          <h2>Un camino para cada respuesta.</h2>
          <p>
            Conecta preguntas y reglas. El modelo decide; el árbol define la
            siguiente acción.
          </p>
        </div>
        <button className="primary" onClick={() => validate(true)}>
          <Save size={16} /> Guardar árbol
        </button>
      </div>
      <div className="toolbar">
        <label>
          Plantilla
          <select
            aria-label="Plantilla de árbol"
            defaultValue="support"
            onChange={(e) => load(e.target.value)}
          >
            <option value="support">Soporte</option>
            <option value="email">Email</option>
            <option value="incident">Incidentes</option>
          </select>
        </label>
        {saved.length ? (
          <label>
            Guardados
            <select
              value=""
              onChange={(e) => {
                const p = saved.find((p) => p.id === e.target.value);
                if (p) onGraph(p.value);
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
        <button onClick={() => add("question")}>
          <Plus size={14} /> Pregunta
        </button>
        <button onClick={() => add("condition")}>
          <Plus size={14} /> Condición
        </button>
        <button onClick={() => add("output")}>
          <Plus size={14} /> Salida
        </button>
        <button onClick={() => validate()}>
          <Check size={15} /> Validar
        </button>
      </div>
      {notice ? <p className="notice">{notice}</p> : null}
      <div className="workflow-layout">
        <div className="flow-surface">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={changeNodes}
            onConnect={connect}
            onNodeClick={(_, n) => setSelected(n.id)}
            fitView
            deleteKeyCode={null}
          >
            <Background color="#c3cdda" gap={20} />
            <Controls />
          </ReactFlow>
        </div>
        <aside className="node-editor">
          <h3>{current ? "Editar nodo" : "Selecciona un nodo"}</h3>
          {current ? (
            <>
              <label>
                ID
                <input value={current.id} disabled />
              </label>
              {current.kind === "question" ? (
                <>
                  <label>
                    Pregunta tipada
                    <textarea
                      value={text}
                      onChange={(e) => setText(e.target.value)}
                      rows={12}
                    />
                  </label>
                  <button
                    onClick={() => {
                      try {
                        update({ question: JSON.parse(text) });
                        setNotice("Pregunta actualizada");
                      } catch {
                        onError("JSON de pregunta inválido");
                      }
                    }}
                  >
                    Aplicar pregunta
                  </button>
                  <label>
                    Siguiente
                    <select
                      value={current.next}
                      onChange={(e) => update({ next: e.target.value })}
                    >
                      {graph?.nodes
                        .filter((n) => n.id !== current.id)
                        .map((n) => (
                          <option key={n.id}>{n.id}</option>
                        ))}
                    </select>
                  </label>
                </>
              ) : current.kind === "condition" ? (
                <>
                  <label>
                    Respuesta origen
                    <select
                      value={current.source}
                      onChange={(e) => update({ source: e.target.value })}
                    >
                      {graph?.nodes
                        .filter((n) => n.kind === "question")
                        .map((n) => (
                          <option key={n.id}>{n.id}</option>
                        ))}
                    </select>
                  </label>
                  <label>
                    Operador
                    <select
                      value={current.operator}
                      onChange={(e) => update({ operator: e.target.value })}
                    >
                      <option value="eq">Igual a</option>
                      <option value="gte">Mayor o igual</option>
                      <option value="lt">Menor que</option>
                    </select>
                  </label>
                  <label>
                    Valor
                    <input
                      value={current.value ?? ""}
                      onChange={(e) =>
                        update({
                          value:
                            current.operator === "eq"
                              ? e.target.value
                              : Number(e.target.value),
                        })
                      }
                    />
                  </label>
                  {(["yes", "no"] as const).map((k) => (
                    <label key={k}>
                      {k === "yes" ? "Si cumple" : "Si no cumple"}
                      <select
                        value={current[k]}
                        onChange={(e) => update({ [k]: e.target.value })}
                      >
                        {graph?.nodes
                          .filter((n) => n.id !== current.id)
                          .map((n) => (
                            <option key={n.id}>{n.id}</option>
                          ))}
                      </select>
                    </label>
                  ))}
                </>
              ) : (
                <label>
                  Acción simulada
                  <input
                    value={current.label}
                    onChange={(e) => update({ label: e.target.value })}
                  />
                </label>
              )}
              <button
                className="danger-text"
                onClick={() => {
                  if (graph) {
                    onGraph({
                      ...graph,
                      nodes: graph.nodes.filter((n) => n.id !== current.id),
                    });
                    setSelected("");
                  }
                }}
              >
                Eliminar nodo
              </button>
            </>
          ) : (
            <p>
              Arrastra conexiones desde los puntos de cada nodo. Valida antes de
              ejecutar.
            </p>
          )}
          <p className="muted">
            Selecciona «Árbol de decisiones» en Arena para ejecutar este diseño.
          </p>
        </aside>
      </div>
    </section>
  );
}
