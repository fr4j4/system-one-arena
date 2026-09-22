import { useEffect, useRef } from "react";

const C = {
  bg: "#111c2b",
  grid: "#223247",
  blue: "#6c9eff",
  cyan: "#43d8cf",
  orange: "#f5ba63",
  text: "#dce7f4",
  red: "#ff7384",
};
export default function GameCanvas({
  state,
}: {
  state: Record<string, any> | undefined;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const frames = useRef<{ previous: any; current: any; at: number }>({
    previous: state,
    current: state,
    at: 0,
  });
  useEffect(() => {
    frames.current = {
      previous: frames.current.current,
      current: state,
      at: performance.now(),
    };
  }, [state]);
  useEffect(() => {
    let id = 0;
    const draw = () => {
      const el = canvas.current;
      if (!el) return;
      const rect = el.getBoundingClientRect(),
        dpr = Math.min(window.devicePixelRatio || 1, 2);
      if (
        el.width !== Math.round(rect.width * dpr) ||
        el.height !== Math.round(rect.height * dpr)
      ) {
        el.width = Math.round(rect.width * dpr);
        el.height = Math.round(rect.height * dpr);
      }
      const ctx = el.getContext("2d");
      if (!ctx) return;
      const w = 760,
        h = 460;
      ctx.setTransform(el.width / w, 0, 0, el.height / h, 0, 0);
      ctx.fillStyle = C.bg;
      ctx.fillRect(0, 0, w, h);
      const f = frames.current,
        s = f.current;
      const t = Math.min(1, (performance.now() - f.at) / 50);
      const lerp = (key: string, index?: number) => {
        const v = index == null ? s[key] : s[key][index];
        const prev =
          index == null ? f.previous?.[key] : f.previous?.[key]?.[index];
        return typeof prev === "number" ? prev + (v - prev) * t : v;
      };
      const box = (
        x: number,
        y: number,
        bw: number,
        bh: number,
        color: string,
        r = 0,
      ) => {
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.roundRect(x, y, bw, bh, r);
        ctx.fill();
      };
      const text = (
        str: string,
        x: number,
        y: number,
        size = 14,
        color = C.text,
        align: CanvasTextAlign = "left",
      ) => {
        ctx.font = `${size}px ui-monospace, monospace`;
        ctx.fillStyle = color;
        ctx.textAlign = align;
        ctx.fillText(str, x, y);
      };
      if (!s) {
        text(
          "Selecciona un escenario para empezar",
          w / 2,
          h / 2,
          17,
          C.text,
          "center",
        );
        id = requestAnimationFrame(draw);
        return;
      }
      if (s.scenario === "snake") {
        const size = 22,
          ox = (w - size * 16) / 2,
          oy = 48;
        ctx.strokeStyle = C.grid;
        ctx.lineWidth = 1;
        for (let i = 0; i <= 16; i++) {
          ctx.beginPath();
          ctx.moveTo(ox + i * size, oy);
          ctx.lineTo(ox + i * size, oy + 16 * size);
          ctx.stroke();
          ctx.beginPath();
          ctx.moveTo(ox, oy + i * size);
          ctx.lineTo(ox + 16 * size, oy + i * size);
          ctx.stroke();
        }
        s.body?.forEach(([x, y]: number[], i: number) =>
          box(
            ox + x * size + 2,
            oy + y * size + 2,
            size - 4,
            size - 4,
            i === 0 ? C.cyan : "#2b817f",
            4,
          ),
        );
        if (s.food) {
          const [x, y] = s.food;
          box(ox + x * size + 5, oy + y * size + 5, 12, 12, C.orange, 4);
        }
        text("16 × 16", ox, 427, 12, "#8194ae");
        text("COMIDA  " + s.score, ox + 352, 427, 12, C.cyan, "right");
      } else if (s.scenario === "tic-tac-toe") {
        const side = 106,
          ox = (w - 318) / 2,
          oy = 66;
        s.board?.forEach((v: number, i: number) => {
          const x = ox + (i % 3) * side,
            y = oy + Math.floor(i / 3) * side;
          box(x + 3, y + 3, 100, 100, C.grid, 8);
          if (v)
            text(
              v === 1 ? "×" : "○",
              x + 53,
              y + 76,
              70,
              v === 1 ? C.cyan : C.orange,
              "center",
            );
          else text(String(i), x + 14, y + 23, 12, "#71859c");
        });
        text("X · MODELO     O · MINIMAX", w / 2, 420, 12, "#91a4be", "center");
      } else if (s.scenario === "pong") {
        const ox = 45,
          oy = 45,
          bw = 670,
          bh = 360;
        ctx.strokeStyle = C.grid;
        ctx.strokeRect(ox, oy, bw, bh);
        ctx.setLineDash([5, 9]);
        ctx.beginPath();
        ctx.moveTo(w / 2, oy);
        ctx.lineTo(w / 2, oy + bh);
        ctx.stroke();
        ctx.setLineDash([]);
        box(ox + 22, oy + ((lerp("paddle") - 6) / 60) * bh, 8, 72, C.cyan, 3);
        box(
          ox + bw - 30,
          oy + ((lerp("opponent") - 6) / 60) * bh,
          8,
          72,
          C.orange,
          3,
        );
        box(
          ox + (lerp("ball", 0) / 100) * bw - 5,
          oy + (lerp("ball", 1) / 60) * bh - 5,
          10,
          10,
          C.text,
          5,
        );
        text("ACIERTOS " + s.hits, ox, 430, 12, C.cyan);
        text("FALLOS " + s.misses, ox + bw, 430, 12, C.orange, "right");
      } else if (s.scenario === "tetris") {
        const size = 19,
          ox = 260,
          oy = 30;
        box(ox - 2, oy - 2, 194, 384, C.grid);
        s.board?.forEach((row: number[], y: number) =>
          row.forEach((v, x) =>
            box(
              ox + x * size + 1,
              oy + y * size + 1,
              size - 2,
              size - 2,
              v ? C.blue : C.bg,
              2,
            ),
          ),
        );
        s.cells?.forEach(([x, y]: number[]) =>
          box(
            ox + (s.x + x) * size + 1,
            oy + (s.y + y) * size + 1,
            size - 2,
            size - 2,
            C.cyan,
            2,
          ),
        );
        text("LÍNEAS", 500, 100, 12, "#8194ae");
        text(String(s.lines), 500, 135, 30, C.text);
        text("PUNTOS", 500, 185, 12, "#8194ae");
        text(String(s.score), 500, 220, 30, C.orange);
      } else if (s.scenario === "fighting") {
        box(55, 70, 270, 8, C.grid, 4);
        box(55, 70, (270 * Math.max(0, s.health)) / 100, 8, C.cyan, 4);
        box(435, 70, 270, 8, C.grid, 4);
        box(435, 70, (270 * Math.max(0, s.enemy_health)) / 100, 8, C.orange, 4);
        text("AGENTE  " + Math.max(0, s.health), 55, 55, 13, C.cyan);
        text(
          "RIVAL  " + Math.max(0, s.enemy_health),
          705,
          55,
          13,
          C.orange,
          "right",
        );
        box(45, 355, 670, 2, C.grid);
        const fighter = (x: number, color: string) => {
          box(50 + x * 6.6 - 17, 250, 34, 68, color, 8);
          box(50 + x * 6.6 - 12, 222, 24, 24, color, 12);
          box(50 + x * 6.6 - 15, 317, 10, 37, color, 3);
          box(50 + x * 6.6 + 5, 317, 10, 37, color, 3);
        };
        fighter(lerp("x"), C.cyan);
        fighter(lerp("enemy_x"), C.orange);
        text(
          "ENERGÍA " +
            Math.round(s.energy) +
            "   COOLDOWN " +
            s.cooldown.toFixed(2) +
            " s",
          55,
          410,
          12,
          "#91a4be",
        );
        text(s.enemy_posture.toUpperCase(), 705, 410, 12, C.orange, "right");
      } else if (s.scenario === "space-invaders") {
        const ox = 65,
          oy = 24,
          bw = 630,
          bh = 400;
        for (let i = 0; i < 35; i++)
          box(((i * 137) % 700) + 30, ((i * 79) % 390) + 25, 1, 1, "#65758a");
        s.enemies?.forEach(([x, y]: number[]) => {
          box(
            ox + (x / 100) * bw - 9,
            oy + (y / 100) * bh - 5,
            18,
            11,
            C.orange,
            2,
          );
          box(ox + (x / 100) * bw - 13, oy + (y / 100) * bh, 4, 7, C.orange);
          box(ox + (x / 100) * bw + 9, oy + (y / 100) * bh, 4, 7, C.orange);
        });
        s.bullets?.forEach(([x, y]: number[]) =>
          box(ox + (x / 100) * bw, oy + (y / 100) * bh, 2, 9, C.cyan),
        );
        s.enemy_bullets?.forEach(([x, y]: number[]) =>
          box(ox + (x / 100) * bw, oy + (y / 100) * bh, 3, 10, C.red),
        );
        const x = ox + (lerp("x") / 100) * bw;
        box(x - 14, oy + 0.9 * bh, 28, 9, C.cyan, 2);
        box(x - 3, oy + 0.9 * bh - 9, 6, 10, C.cyan, 2);
        text("VIDAS " + s.lives, 55, 443, 12, C.cyan);
        text("PUNTOS " + s.score, 705, 443, 12, C.orange, "right");
      }
      if (s.done) {
        box(190, 173, 380, 102, "#111c2bec", 10);
        text("EPISODIO COMPLETADO", w / 2, 212, 15, C.text, "center");
        text(
          String(s.outcome ?? "")
            .replaceAll("_", " ")
            .toUpperCase(),
          w / 2,
          245,
          18,
          C.cyan,
          "center",
        );
      }
      id = requestAnimationFrame(draw);
    };
    id = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(id);
  }, []);
  return (
    <canvas
      ref={canvas}
      className="game-canvas"
      aria-label={`Estado del juego ${state?.scenario ?? ""}`}
      role="img"
    />
  );
}
