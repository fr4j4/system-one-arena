import { useEffect, useRef } from "react";
import type { Settings, Frame } from "./types";
const HOLDS = new Set([
  "forward",
  "back",
  "crouch",
  "guard_high",
  "guard_low",
  "charge",
]);
export function useControls(
  enabled: boolean,
  settings: Settings,
  input: (a: string, release?: boolean) => void,
  frameRef: React.RefObject<Frame | null>,
  pause: () => void,
) {
  const latest = useRef({ input, pause, settings });
  latest.current = { input, pause, settings };
  useEffect(() => {
    if (!enabled) return;
    const held = new Map<string, string>();
    let previousButtons: boolean[] = [],
      lastHold = "",
      lastTime = 0,
      raf = 0;
    const actionFor = (code: string) => latest.current.settings.bindings[code];
    const translate = (action: string) => {
      const frame = frameRef.current;
      if (frame?.phase === "clash")
        return (
          (
            {
              light: "hold",
              heavy: "push",
              signature: "surge",
              back: "yield",
            } as Record<string, string>
          )[action] ?? action
        );
      if (frame?.phase === "finish")
        return action === "light"
          ? "finish"
          : action === "heavy"
            ? "spare"
            : action;
      return [...held.values()].includes("crouch") && action === "guard_high"
        ? "guard_low"
        : [...held.values()].includes("crouch") && action === "light"
          ? "low"
          : action;
    };
    const down = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.matches("input,select,textarea")) return;
      if (e.code === "Escape") {
        e.preventDefault();
        latest.current.pause();
        return;
      }
      let a = actionFor(e.code);
      if (a === "jump") {
        if ([...held.values()].includes("forward")) a = "jump_forward";
        else if ([...held.values()].includes("back")) a = "jump_back";
      }
      if (!a) return;
      e.preventDefault();
      if (e.repeat) return;
      held.set(e.code, a);
      latest.current.input(translate(a));
    };
    const up = (e: KeyboardEvent) => {
      if (!held.has(e.code)) return;
      e.preventDefault();
      held.delete(e.code);
      latest.current.input("neutral", true);
    };
    const release = () => {
      held.clear();
      lastHold = "";
      latest.current.input("neutral", true);
    };
    const blur = () => {
      release();
      latest.current.pause();
    };
    const poll = (now: number) => {
      const pad = navigator.getGamepads?.().find((p) => p?.connected);
      let padHold = "";
      if (pad) {
        const map = latest.current.settings.gamepad;
        for (const [id, a] of Object.entries(map)) {
          const n = +id,
            pressed = !!pad.buttons[n]?.pressed;
          if (pressed && !previousButtons[n]) {
            if (a === "pause") latest.current.pause();
            else latest.current.input(translate(a));
          }
          if (pressed && HOLDS.has(a)) padHold = a;
          previousButtons[n] = pressed;
        }

        if (Math.abs(pad.axes[0] ?? 0) > 0.3)
          padHold = pad.axes[0] > 0 ? "forward" : "back";
      }
      const keyHold =
        [...held.values()].reverse().find((a) => HOLDS.has(a)) ?? "";
      const a = translate(padHold || keyHold);
      if (a && now - lastTime > 120) {
        latest.current.input(a);
        lastTime = now;
      }
      if (lastHold && !a) latest.current.input("neutral", true);
      lastHold = a;
      raf = requestAnimationFrame(poll);
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    window.addEventListener("blur", blur);
    raf = requestAnimationFrame(poll);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      window.removeEventListener("blur", blur);
      cancelAnimationFrame(raf);
      release();
    };
  }, [enabled, input, frameRef]);
}
