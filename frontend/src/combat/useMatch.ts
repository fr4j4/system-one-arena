import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Frame, type Match } from "./types";
const LIVE = ["preparing", "running", "paused"];
export function useMatch(onError: (s: string) => void) {
  const [match, setMatch] = useState<Match | null>(null),
    [frame, setFrame] = useState<Frame | null>(null),
    [events, setEvents] = useState<any[]>([]);
  const frameRef = useRef<Frame | null>(null),
    socket = useRef<WebSocket | null>(null),
    current = useRef<Match | null>(null),
    lastPaint = useRef(0),
    inputSeq = useRef(0),
    generation = useRef(0);
  const preview = useCallback((s: Frame) => {
    if (!current.current) {
      frameRef.current = { ...s, preview: true };
      setFrame(frameRef.current);
    }
  }, []);
  const attach = useCallback(
    (m: Match) => {
      generation.current++;
      const gen = generation.current;
      socket.current?.close();
      current.current = m;
      setMatch(m);
      setEvents([]);
      if (m.state) {
        frameRef.current = m.state;
        setFrame(m.state);
      }
      if (!LIVE.includes(m.status)) return;
      const role = m.config.players.some((p) => p.controller === "human")
        ? "controller"
        : "spectator";
      const url = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/v2/matches/${m.id}/live?role=${role}`;
      let attempt = 0,
        warned = false;
      const warn = (s: string) => {
        if (warned || gen !== generation.current) return;
        warned = true;
        onError(s);
      };
      const connect = () => {
        const ws = new WebSocket(url);
        socket.current = ws;
        ws.onopen = () => {
          attempt = 0;
          if (warned) onError("");
          warned = false;
        };
        ws.onmessage = async ({ data }) => {
          if (gen !== generation.current) return;
          const e = JSON.parse(data);
          if (e.kind === "initial" || e.kind === "finished") {
            const next = e.match;
            current.current = next;
            setMatch(next);
            if (next.state) {
              frameRef.current = {
                ...next.state,
                paused: next.status !== "running",
              };
              setFrame(frameRef.current);
            }
          } else if (e.kind === "snapshot") {
            frameRef.current = {
              ...e.state,
              paused:
                current.current?.status === "paused" ||
                current.current?.status === "stopped",
            };
            if (performance.now() - lastPaint.current > 80 || e.state.done) {
              lastPaint.current = performance.now();
              setFrame(frameRef.current);
            }
          } else if (e.kind === "status") {
            setMatch((old) => {
              if (!old) return old;
              const next = { ...old, status: e.status, error: e.error };
              current.current = next;
              return next;
            });
            if (frameRef.current)
              frameRef.current = {
                ...frameRef.current,
                paused: e.status !== "running",
              };
          } else if (e.kind === "metrics") {
            setMatch((old) => {
              if (!old) return old;
              const next = { ...old, status: e.status, players: e.players };
              current.current = next;
              return next;
            });
          } else if (e.kind === "ready") {
            setMatch((old) => {
              if (!old) return old;
              const next = { ...old, status: "running" };
              current.current = next;
              return next;
            });
          } else if (e.kind === "error") onError(e.error);
          else if (e.kind === "resync") {
            let refreshed: Match;
            try {
              refreshed = await api<Match>("/matches/" + m.id);
            } catch (err) {
              if (gen === generation.current) onError(String(err));
              return;
            }
            if (gen === generation.current) {
              current.current = refreshed;
              setMatch(refreshed);
              if (refreshed.state) {
                frameRef.current = refreshed.state;
                setFrame(refreshed.state);
              }
            }
          }
          if (!["snapshot", "metrics", "initial"].includes(e.kind))
            setEvents((old) => [...old.slice(-99), e]);
        };
        ws.onerror = () =>
          warn("No se pudo conectar con la partida. Revisa el servidor.");
        ws.onclose = () => {
          if (
            gen !== generation.current ||
            !LIVE.includes(current.current?.status ?? "")
          )
            return;
          // Refresh status over HTTP, then reconnect with capped backoff while
          // the match is still live; the "initial" message resyncs the state.
          const delay = Math.min(5000, 250 * 2 ** attempt++);
          void api<Match>("/matches/" + m.id)
            .then((next) => {
              if (gen !== generation.current) return;
              current.current = next;
              setMatch(next);
              return LIVE.includes(next.status);
            })
            .catch(() => {
              warn(
                "Conexión perdida. La partida puede seguir activa; reconecta para detenerla.",
              );
              return true;
            })
            .then((retry) => {
              if (retry)
                setTimeout(
                  () => gen === generation.current && connect(),
                  delay,
                );
            });
        };
      };
      connect();
    },
    [onError],
  );
  const command = useCallback(
    async (name: string) => {
      if (!current.current) return;
      try {
        const m = await api<Match>(`/matches/${current.current.id}/control`, {
          command: name,
        });
        if (current.current?.id !== m.id) return;
        if (
          ["completed", "stopped", "failed"].includes(current.current.status) &&
          ["running", "paused", "preparing"].includes(m.status)
        )
          return;
        current.current = m;
        setMatch(m);
        if (frameRef.current) {
          frameRef.current = {
            ...frameRef.current,
            paused: m.status !== "running",
          };
          setFrame(frameRef.current);
        }
      } catch (e) {
        onError(String(e));
      }
    },
    [onError],
  );
  const input = useCallback((action: string, release = false) => {
    const m = current.current;
    if (!m || m.status !== "running" || socket.current?.readyState !== 1)
      return;
    const player = m.config.players.findIndex((p) => p.controller === "human");
    if (player < 0) return;
    socket.current.send(
      JSON.stringify({
        kind: "input",
        player,
        action,
        release,
        seq: ++inputSeq.current,
      }),
    );
  }, []);
  const clear = useCallback(() => {
    generation.current++;
    socket.current?.close();
    socket.current = null;
    current.current = null;
    setMatch(null);
    setEvents([]);
  }, []);
  useEffect(
    () => () => {
      generation.current++;
      socket.current?.close();
    },
    [],
  );
  return {
    match,
    frame,
    frameRef,
    events,
    preview,
    attach,
    command,
    input,
    clear,
  };
}
