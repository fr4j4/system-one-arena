import { memo, useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { createRig } from "./rig";
import { createStage } from "./stage";
import { COLORS, createPowers } from "./powers";
import type { Frame, Settings } from "./types";
import type { CombatAudio } from "./audio";
type Props = {
  frameRef: React.RefObject<Frame | null>;
  characters: string[];
  arena: string;
  settings: Settings;
  audio: CombatAudio;
  onReady: (ready: boolean) => void;
  onError: (error: string) => void;
};
export default memo(function Scene({
  frameRef,
  characters,
  arena,
  settings,
  audio,
  onReady,
  onError,
}: Props) {
  const host = useRef<HTMLDivElement>(null),
    options = useRef(settings);
  options.current = settings;
  const [loading, setLoading] = useState(true),
    [failure, setFailure] = useState("");
  const key = characters.join(":");
  useEffect(() => {
    let disposed = false,
      cleanup = () => {};
    setLoading(true);
    setFailure("");
    onReady(false);
    const init = async () => {
      const container = host.current!;
      let renderer: THREE.WebGLRenderer;
      try {
        renderer = new THREE.WebGLRenderer({
          antialias: settings.quality !== "low",
          powerPreference: "high-performance",
        });
      } catch {
        throw new Error(
          "WebGL2 no está disponible. Activa la aceleración gráfica para entrar a la arena.",
        );
      }
      const gl = renderer;
      gl.setPixelRatio(
        Math.min(
          devicePixelRatio,
          settings.quality === "high"
            ? 1.75
            : settings.quality === "medium"
              ? 1.3
              : 1,
        ),
      );
      gl.shadowMap.enabled = settings.quality !== "low";
      gl.shadowMap.type = THREE.PCFShadowMap;
      gl.toneMapping = THREE.ACESFilmicToneMapping;
      gl.toneMappingExposure = 1.15;
      gl.domElement.dataset.renderer = "combat-three";
      gl.domElement.setAttribute("aria-label", "Arena 3D de combate");
      gl.domElement.setAttribute("role", "img");
      container.appendChild(gl.domElement);
      const scene = new THREE.Scene(),
        camera = new THREE.PerspectiveCamera(36, 1, 0.1, 120);
      camera.position.set(0, 3.7, 17);
      camera.lookAt(0, 1.25, 0);
      const stage = createStage(scene, arena, settings.quality);
      let raf = 0;
      const observer = new ResizeObserver(() => {
        const w = Math.max(1, container.clientWidth),
          h = Math.max(1, container.clientHeight);
        gl.setSize(w, h, false);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
      });
      observer.observe(container);
      let cleaned = false;
      const cleanupBase = () => {
        if (cleaned) return;
        cleaned = true;
        cancelAnimationFrame(raf);
        observer.disconnect();
        const geometries = new Set<THREE.BufferGeometry>(),
          materials = new Set<THREE.Material>();
        scene.traverse((o) => {
          const m = o as THREE.Mesh;
          if (m.geometry) geometries.add(m.geometry);
          if (m.material)
            (Array.isArray(m.material) ? m.material : [m.material]).forEach(
              (x) => materials.add(x),
            );
        });
        geometries.forEach((g) => g.dispose());
        materials.forEach((m) => m.dispose());
        stage.sun.shadow.dispose();
        gl.dispose();
        gl.forceContextLoss();
        gl.domElement.remove();
      };
      cleanup = cleanupBase;
      const settled = await Promise.allSettled(
        characters.map((id) => createRig(id)),
      );
      const failed = settled.find((r) => r.status === "rejected");
      const rigs = settled.flatMap((r) =>
        r.status === "fulfilled" ? [r.value] : [],
      );
      if (failed) {
        rigs.forEach((r) => r.dispose());
        throw failed.reason;
      }
      if (disposed) {
        rigs.forEach((r) => r.dispose());
        cleanupBase();
        return;
      }
      rigs.forEach((r) => scene.add(r.root));
      const powers = createPowers(scene, characters);
      const auraGeo = new THREE.TorusGeometry(0.64, 0.023, 6, 64),
        auraMats = characters.map(
          (c) =>
            new THREE.MeshBasicMaterial({
              color: COLORS[c],
              transparent: true,
              opacity: 0.25,
              blending: THREE.AdditiveBlending,
              depthWrite: false,
            }),
        );
      const auras = rigs.map((r, i) => {
        const group = new THREE.Group();
        for (let j = 0; j < 3; j++) {
          const ring = new THREE.Mesh(auraGeo, auraMats[i]);
          ring.rotation.x = Math.PI / 2;
          ring.position.y = 0.1 + j * 0.65;
          group.add(ring);
        }
        scene.add(group);
        return group;
      });
      const boltGeo = new THREE.IcosahedronGeometry(0.16, 1),
        beamGeo = new THREE.CylinderGeometry(1, 1, 1, 10),
        powerMats = characters.map(
          (c) =>
            new THREE.MeshBasicMaterial({
              color: COLORS[c],
              blending: THREE.AdditiveBlending,
              transparent: true,
              opacity: 0.9,
              depthWrite: false,
            }),
        );
      const shots = new Map<number, THREE.Mesh>();
      const clashBeams = characters.map((_, i) => {
        const mesh = new THREE.Mesh(beamGeo, powerMats[i]);
        scene.add(mesh);
        return mesh;
      });
      const ball = new THREE.Mesh(
        new THREE.SphereGeometry(1, 24, 16),
        new THREE.MeshBasicMaterial({
          color: 0xeeefff,
          transparent: true,
          opacity: 0.85,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
        }),
      );
      scene.add(ball);
      const particleCount =
        settings.quality === "low"
          ? 72
          : settings.quality === "medium"
            ? 180
            : 320;
      const particles = new THREE.InstancedMesh(
        new THREE.OctahedronGeometry(0.045),
        new THREE.MeshBasicMaterial({
          color: 0xffffff,
          transparent: true,
          opacity: 0.8,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
        }),
        particleCount,
      );
      particles.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      particles.frustumCulled = false;
      scene.add(particles);
      const sparks = Array.from({ length: particleCount }, () => ({
        x: 0,
        y: -100,
        z: 0,
        vx: 0,
        vy: 0,
        vz: 0,
        life: 0,
        max: 1,
        zeroed: false,
        color: new THREE.Color(),
      }));
      let cursor = 0;
      const dummy = new THREE.Object3D();
      const burst = (
        x: number,
        y: number,
        color: number,
        seed: number,
        count = 22,
      ) => {
        if (options.current.reducedFlash) count = Math.min(count, 8);
        for (let j = 0; j < count; j++) {
          const s = sparks[cursor++ % particleCount],
            v = Math.sin((seed + j) * 127.1) * 43758.5,
            a = (v - Math.floor(v)) * Math.PI * 2;
          s.x = x;
          s.y = y;
          s.z = 0.15;
          s.vx = Math.cos(a) * (1 + (j % 4));
          s.vy = Math.sin(a) * 3 + 2;
          s.vz = Math.sin(j * 2) * 1.2;
          s.life = s.max = 0.25 + (j % 5) * 0.09;
          s.zeroed = false;
          s.color.setHex(color);
        }
      };
      const up = new THREE.Vector3(0, 1, 0),
        direction = new THREE.Vector3(),
        black = new THREE.Color(0),
        hurtColors = characters.map((c) =>
          new THREE.Color(COLORS[c]).multiplyScalar(0.3),
        ),
        hurtShown = characters.map((): boolean | null => null);
      const beam = (
        mesh: THREE.Mesh,
        x1: number,
        y1: number,
        x2: number,
        y2: number,
        width: number,
      ) => {
        direction.set(x2 - x1, y2 - y1, 0);
        mesh.position.set((x1 + x2) / 2, (y1 + y2) / 2, 0.02);
        mesh.scale.set(width, direction.length(), width);
        mesh.quaternion.setFromUnitVectors(up, direction.normalize());
      };
      let previous: Frame | null = null,
        current: Frame | null = null,
        arrival = 0,
        lastTime = performance.now(),
        presentation = 0,
        lastPresentation = 0,
        lastSeq = 0,
        lastPhase = "",
        shake = 0,
        frameCount = 0,
        measureStart = performance.now(),
        slowFrames = 0;
      const contextLost = (e: Event) => {
        e.preventDefault();
        setFailure(
          "Se perdió el contexto gráfico. Recarga para restaurar la arena.",
        );
        onReady(false);
        onError("La vista 3D se desconectó; la partida se ha pausado.");
      };
      gl.domElement.addEventListener("webglcontextlost", contextLost);
      const render = (now: number) => {
        if (disposed) return;
        const state = frameRef.current;
        const realDt = Math.min(0.05, (now - lastTime) / 1000);
        lastTime = now;
        if (state && state !== current) {
          previous = current ?? state;
          current = state;
          arrival = now;
          if (state.tick < previous.tick) {
            lastSeq = 0;
            sparks.forEach((p) => (p.life = 0));
          }
        }
        if (current) {
          const s = current,
            alpha = Math.min(1, (now - arrival) / 33.33);
          presentation = s.preview
            ? now / 1000
            : THREE.MathUtils.lerp(previous?.tick ?? s.tick, s.tick, alpha) /
              60;
          const dt = Math.max(
            0,
            Math.min(0.1, presentation - lastPresentation),
          );
          lastPresentation = presentation;
          if (!s.preview) audio.consume(s);
          for (const e of s.events ?? []) {
            if (e.seq <= lastSeq) continue;
            lastSeq = e.seq;
            if (["hit", "block", "parry", "power_collision"].includes(e.kind)) {
              const target = s.fighters.find(
                (f: any) => f.id === (e.target ?? e.player_id),
              );
              burst(
                e.x ?? target?.x ?? 0,
                e.y ?? 1,
                COLORS[target?.character ?? characters[0]],
                e.seq,
                e.kind === "parry" ? 35 : 22,
              );
              if (e.kind === "hit") shake = 0.09;
            }
            if (e.kind === "clash_pulse") {
              burst(0, 1.2, 0xe7dbff, e.seq, 40);
              shake = 0.13;
            }
          }
          if (s.phase !== lastPhase) {
            if (s.phase === "finisher") {
              burst(
                s.fighters.find((f: any) => f.id !== s.winner)?.x ?? 0,
                1.3,
                COLORS[
                  s.fighters.find((f: any) => f.id === s.winner)?.character ??
                    characters[0]
                ],
                s.tick,
                particleCount * 0.5,
              );
            }
            lastPhase = s.phase;
          }
          stage.animate(options.current.reducedMotion ? 0 : presentation);
          powers.update(
            s,
            presentation,
            options.current.reducedMotion || options.current.reducedFlash,
          );
          rigs.forEach((rig, i) => {
            const f = s.fighters[i];
            if (!f) return;
            const before =
              previous?.round === s.round ? previous.fighters[i] : f;
            const fallen =
              (f.knockdown > 0 || f.health <= 0) &&
              !["finish", "finisher"].includes(s.phase);
            rig.root.position.set(
              THREE.MathUtils.lerp(before?.x ?? f.x, f.x, alpha),
              THREE.MathUtils.lerp(before?.y ?? f.y, f.y, alpha) -
                (fallen ? 0.75 : 0),
              0,
            );
            rig.root.rotation.y = f.facing * 1.25;
            let pose = fallen
              ? "knockdown"
              : f.action === "forward" || f.action === "back"
                ? "walk"
                : f.action === "guard_break"
                  ? "hurt"
                  : f.action === "thrown"
                    ? "hurt"
                    : f.action === "neutral"
                      ? "idle"
                      : f.action;
            if (s.phase === "intro") pose = "idle";
            if (s.phase === "finished" && f.id === s.winner) pose = "victory";
            if (s.phase === "finish") pose = f.health <= 0 ? "hurt" : "victory";
            if (s.phase === "finisher")
              pose = f.id === s.winner ? "finisher" : "hurt";
            if (s.phase === "clash") pose = "beam";
            let progress: number | undefined = undefined;
            if (f.move_timing) {
              const t = f.move_timing;
              progress = t.frame / (t.startup + t.active + t.recovery);
            }
            if (s.phase === "finisher") progress = 1 - s.phase_left / 300;
            rig.animate(pose, presentation, progress);
            const dissolve =
              s.phase === "finisher" && f.id !== s.winner
                ? Math.max(0, 1 - (1 - s.phase_left / 300) * 1.7)
                : 1;
            rig.root.scale.setScalar(Math.max(0.001, dissolve));
            rig.root.visible = dissolve > 0.02;
            const hurt = !!f.hurt && !options.current.reducedFlash;
            if (hurt !== hurtShown[i]) {
              hurtShown[i] = hurt;
              rig.materials.forEach((m) => {
                if (m.name !== "energy")
                  m.emissive.copy(hurt ? hurtColors[i] : black);
              });
            }
            auras[i].position.copy(rig.root.position);
            auras[i].visible = f.energy >= 90 || f.action === "charge";
            auraMats[i].opacity = options.current.reducedFlash
              ? 0.12
              : 0.18 + Math.sin(presentation * 6) * 0.07 + f.energy / 1000;
            auras[i].scale.setScalar(1 + f.energy / 250);
            auras[i].rotation.y = presentation;
          });
          const ids = new Set<number>();
          for (const p of s.projectiles) {
            ids.add(p.id);
            let object = shots.get(p.id);
            if (!object) {
              object = new THREE.Mesh(
                p.kind === "beam" ? beamGeo : boltGeo,
                powerMats[p.owner],
              );
              scene.add(object);
              shots.set(p.id, object);
            }
            const old = previous?.projectiles.find((v: any) => v.id === p.id);
            const x = THREE.MathUtils.lerp(old?.x ?? p.x, p.x, alpha);
            if (p.kind === "beam") beam(object, p.origin, p.y, x, p.y, 0.095);
            else {
              object.position.set(x, p.y, 0);
              object.scale.set(1.8, 1, 1);
              object.rotation.x = presentation * 9;
            }
          }
          for (const [id, object] of shots)
            if (!ids.has(id)) {
              scene.remove(object);
              shots.delete(id);
            }
          clashBeams.forEach((o) => (o.visible = s.phase === "clash"));
          ball.visible =
            s.phase === "clash" ||
            s.phase === "finisher" ||
            s.phase === "cinematic";
          if (s.phase === "clash") {
            const middle =
              (s.fighters[0].x + s.fighters[1].x) / 2 +
              (s.clash.score[0] - s.clash.score[1]) * 0.16;
            clashBeams.forEach((o, i) =>
              beam(
                o,
                s.fighters[i].x,
                s.fighters[i].y + 1.5,
                middle,
                1.5,
                0.12 + Math.sin(presentation * 14) * 0.015,
              ),
            );
            ball.position.set(middle, 1.5, 0);
            ball.scale.setScalar(0.35 + Math.sin(presentation * 20) * 0.025);
          } else if (ball.visible) {
            const winner =
              s.fighters.find(
                (f: any) => f.id === (s.winner ?? s.cinematic?.player_id),
              ) ?? s.fighters[0];
            const opponent = s.fighters.find((f: any) => f.id !== winner.id)!;
            ball.position.set(opponent.x, 1.3, 0);
            const progress =
              s.phase === "finisher"
                ? 1 - s.phase_left / 300
                : 1 - s.phase_left / 90;
            ball.scale.setScalar(
              Math.sin(progress * Math.PI) * (s.phase === "finisher" ? 2.1 : 1),
            );
            (ball.material as THREE.MeshBasicMaterial).color.setHex(
              COLORS[winner.character],
            );
            if (!s.paused && frameCount % 4 === 0)
              burst(opponent.x, 1.2, COLORS[winner.character], s.tick, 8);
          }
          // Dead slots are zeroed once; upload only when a slot changed.
          let sparksChanged = false;
          sparks.forEach((p, i) => {
            if (p.life > 0) {
              p.life = Math.max(0, p.life - dt);
              p.x += p.vx * dt;
              p.y += p.vy * dt;
              p.z += p.vz * dt;
              p.vy -= 6 * dt;
              dummy.position.set(p.x, p.y, p.z);
              dummy.scale.setScalar((p.life / p.max) * (1 + p.max));
            } else if (!p.zeroed) {
              p.zeroed = true;
              dummy.position.set(0, -100, 0);
              dummy.scale.setScalar(0);
            } else return;
            sparksChanged = true;
            dummy.updateMatrix();
            particles.setMatrixAt(i, dummy.matrix);
            particles.setColorAt(i, p.color);
          });
          if (sparksChanged) {
            particles.instanceMatrix.needsUpdate = true;
            if (particles.instanceColor)
              particles.instanceColor.needsUpdate = true;
          }
          const [a, b] = s.fighters;
          let targetX = (a.x + b.x) / 2;
          const span = Math.abs(a.x - b.x) + 5;
          let z = Math.max(
            11.5,
            span / (2 * Math.tan(THREE.MathUtils.degToRad(18)) * camera.aspect),
          );
          if (
            ["finisher", "cinematic"].includes(s.phase) &&
            !options.current.reducedMotion
          ) {
            z = Math.max(8, z * 0.76);
            targetX = (a.x + b.x) / 2;
          }
          camera.position.x = THREE.MathUtils.lerp(
            camera.position.x,
            targetX,
            0.07,
          );
          camera.position.z = THREE.MathUtils.lerp(camera.position.z, z, 0.05);
          camera.position.y = THREE.MathUtils.lerp(
            camera.position.y,
            s.phase === "finisher" ? 2.8 : 3.6,
            0.06,
          );
          shake = Math.max(0, shake - realDt * 0.35);
          camera.lookAt(
            targetX,
            1.3 +
              (options.current.shake && !options.current.reducedMotion
                ? Math.sin(now * 0.1) * shake
                : 0),
            0,
          );
        }
        gl.render(scene, camera);
        frameCount++;
        if (now - measureStart > 2000) {
          const fps = (frameCount * 1000) / (now - measureStart);
          gl.domElement.dataset.fps = fps.toFixed(1);
          gl.domElement.dataset.drawCalls = String(gl.info.render.calls);
          gl.domElement.dataset.geometries = String(gl.info.memory.geometries);
          if (fps < 42) slowFrames++;
          else slowFrames = 0;
          if (slowFrames >= 3 && gl.getPixelRatio() > 1) {
            gl.setPixelRatio(Math.max(1, gl.getPixelRatio() - 0.25));
            slowFrames = 0;
          }
          frameCount = 0;
          measureStart = now;
        }
        raf = requestAnimationFrame(render);
      };
      raf = requestAnimationFrame(render);
      setLoading(false);
      onReady(true);
      cleanup = () => {
        gl.domElement.removeEventListener("webglcontextlost", contextLost);
        rigs.forEach((r) => r.dispose());
        auraGeo.dispose();
        boltGeo.dispose();
        beamGeo.dispose();
        auraMats.forEach((m) => m.dispose());
        powerMats.forEach((m) => m.dispose());
        cleanupBase();
      };
    };
    init().catch((e) => {
      if (!disposed) {
        cleanup();
        setFailure(String(e));
        setLoading(false);
        onReady(false);
        onError(String(e));
      }
    });
    return () => {
      disposed = true;
      cleanup();
    };
  }, [key, arena, settings.quality, frameRef, onReady, onError, audio]);
  return (
    <div className="combat-scene" ref={host}>
      {loading && (
        <div className="scene-loading">
          <span className="loading-orbit" />
          <b>Preparando la arena</b>
          <small>Cargando personajes y animaciones</small>
        </div>
      )}
      {failure && (
        <div className="scene-failure" role="alert">
          {failure}
        </div>
      )}
    </div>
  );
});
