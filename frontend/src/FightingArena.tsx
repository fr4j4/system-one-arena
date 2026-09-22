import { useEffect, useRef, useState } from "react";
import * as THREE from "three";

const COLORS = [0xff7740, 0x43d8ff];
const MOVE_NAMES: Record<string, string> = {
  neutral: "Guardia libre",
  approach: "Avanzar",
  retreat: "Retroceder",
  block: "Bloquear",
  jump: "Salto",
  attack: "Puño",
  heavy: "Patada",
  projectile: "Proyectil",
  special: "Onda de poder",
  hurt: "Impacto",
};

function fighter(color: number) {
  const root = new THREE.Group();
  const armor = new THREE.MeshStandardMaterial({
    color: 0x263343,
    metalness: 0.72,
    roughness: 0.35,
  });
  const dark = new THREE.MeshStandardMaterial({
    color: 0x101827,
    roughness: 0.75,
  });
  const accent = new THREE.MeshStandardMaterial({
    color,
    metalness: 0.45,
    roughness: 0.3,
    emissive: color,
    emissiveIntensity: 0.45,
  });
  const glow = new THREE.MeshBasicMaterial({ color });
  function mesh(
    geometry: THREE.BufferGeometry,
    material: THREE.Material,
    x: number,
    y: number,
    z: number,
    parent: THREE.Object3D = root,
  ) {
    const m = new THREE.Mesh(geometry, material);
    m.position.set(x, y, z);
    m.castShadow = true;
    m.receiveShadow = true;
    parent.add(m);
    return m;
  }
  mesh(new THREE.CapsuleGeometry(0.34, 0.65, 4, 10), armor, 0, 1.62, 0);
  mesh(new THREE.BoxGeometry(0.6, 0.38, 0.46), dark, 0, 1.1, 0);
  const chest = mesh(new THREE.OctahedronGeometry(0.23), accent, 0, 1.7, 0.31);
  chest.scale.set(1, 1.35, 0.4);
  mesh(new THREE.SphereGeometry(0.27, 12, 8), armor, 0, 2.36, 0).scale.set(
    0.93,
    1.1,
    0.95,
  );
  mesh(new THREE.BoxGeometry(0.4, 0.09, 0.12), glow, 0, 2.4, 0.235);
  mesh(new THREE.BoxGeometry(0.32, 0.13, 0.14), dark, 0, 2.19, 0.23);
  mesh(new THREE.BoxGeometry(0.65, 0.1, 0.48), accent, 0, 1.08, 0);
  const arms: THREE.Group[] = [],
    legs: THREE.Group[] = [];
  for (const side of [-1, 1]) {
    const arm = new THREE.Group();
    arm.position.set(side * 0.46, 1.99, 0);
    root.add(arm);
    mesh(new THREE.SphereGeometry(0.21, 10, 8), accent, 0, 0, 0, arm);
    mesh(new THREE.CapsuleGeometry(0.12, 0.45, 3, 8), dark, 0, -0.32, 0, arm);
    mesh(new THREE.BoxGeometry(0.24, 0.34, 0.27), armor, 0, -0.7, 0.03, arm);
    mesh(new THREE.SphereGeometry(0.16, 8, 8), accent, 0, -0.94, 0.08, arm);
    arms.push(arm);
    const leg = new THREE.Group();
    leg.position.set(side * 0.21, 1.03, 0);
    root.add(leg);
    mesh(new THREE.CapsuleGeometry(0.15, 0.48, 3, 8), dark, 0, -0.32, 0, leg);
    mesh(new THREE.BoxGeometry(0.24, 0.35, 0.25), armor, 0, -0.69, 0.01, leg);
    mesh(new THREE.BoxGeometry(0.28, 0.16, 0.43), accent, 0, -0.96, 0.13, leg);
    legs.push(leg);
  }
  const shield = mesh(
    new THREE.TorusGeometry(0.85, 0.035, 6, 36),
    glow,
    0,
    1.35,
    0.6,
  );
  shield.visible = false;
  return { root, arms, legs, shield, armor, accent };
}

export default function FightingArena({
  state,
}: {
  state: Record<string, any>;
}) {
  const host = useRef<HTMLDivElement>(null),
    frames = useRef({ previous: state, current: state, at: 0 });
  const [error, setError] = useState("");
  useEffect(() => {
    frames.current = {
      previous: frames.current.current,
      current: state,
      at: performance.now(),
    };
  }, [state]);
  useEffect(() => {
    const container = host.current!;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    } catch {
      setError(
        "No se pudo activar WebGL. El combate y la telemetría siguen disponibles; prueba un navegador con aceleración gráfica.",
      );
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.45;
    renderer.domElement.setAttribute("aria-label", "Combate 3D en plano 2D");
    renderer.domElement.setAttribute("role", "img");
    renderer.domElement.dataset.renderer = "threejs";
    container.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x080e1b);
    scene.fog = new THREE.Fog(0x080e1b, 35, 100);
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
    camera.position.set(0, 4.3, 16);
    camera.lookAt(0, 1.1, 0);
    scene.add(new THREE.HemisphereLight(0xb4d7ff, 0x151b2b, 2.8));
    const key = new THREE.DirectionalLight(0xffebd1, 3.5);
    key.position.set(-3, 10, 6);
    key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024);
    Object.assign(key.shadow.camera, {
      left: -11,
      right: 11,
      top: 7,
      bottom: -7,
    });
    scene.add(key);
    const rim = new THREE.DirectionalLight(0x5bcaff, 2.5);
    rim.position.set(3, 4, -5);
    scene.add(rim);
    const floorMaterial = new THREE.MeshStandardMaterial({
      color: 0x1c293b,
      roughness: 0.65,
      metalness: 0.3,
    });
    const floor = new THREE.Mesh(
      new THREE.BoxGeometry(20, 0.35, 8),
      floorMaterial,
    );
    floor.position.y = -0.22;
    floor.receiveShadow = true;
    scene.add(floor);
    const grid = new THREE.GridHelper(20, 20, 0x395b79, 0x223950);
    grid.position.y = -0.035;
    scene.add(grid);
    const stripGeometry = new THREE.BoxGeometry(18, 0.035, 0.055);
    for (const z of [-1.8, 1.8]) {
      const strip = new THREE.Mesh(
        stripGeometry,
        new THREE.MeshBasicMaterial({ color: 0x487b9f }),
      );
      strip.position.set(0, 0.005, z);
      scene.add(strip);
    }
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(2.1, 0.035, 8, 80),
      new THREE.MeshBasicMaterial({ color: 0x315877 }),
    );
    ring.position.set(0, 3, -4);
    scene.add(ring);
    const core = new THREE.Mesh(
      new THREE.OctahedronGeometry(0.75),
      new THREE.MeshStandardMaterial({
        color: 0x213e59,
        emissive: 0x17364c,
        metalness: 0.8,
        roughness: 0.25,
      }),
    );
    core.position.set(0, 3, -4);
    scene.add(core);
    for (let i = 0; i < 8; i++) {
      const x = (i - 3.5) * 2.5;
      const pillar = new THREE.Mesh(
        new THREE.BoxGeometry(0.35, 5.8, 0.5),
        floorMaterial,
      );
      pillar.position.set(x, 2.7, -5);
      scene.add(pillar);
      const light = new THREE.Mesh(
        new THREE.BoxGeometry(0.055, 3.3, 0.055),
        new THREE.MeshBasicMaterial({ color: i < 4 ? 0x8d4930 : 0x2b677e }),
      );
      light.position.set(x, 2.4, -4.7);
      scene.add(light);
    }
    const fighters = COLORS.map((color) => {
      const f = fighter(color);
      scene.add(f.root);
      return f;
    });
    const shotGeometry = new THREE.IcosahedronGeometry(0.25, 1);
    const shotMaterials = COLORS.map(
      (color) => new THREE.MeshBasicMaterial({ color }),
    );
    const shots = new Map<number, THREE.Mesh>();
    const impactGeometry = new THREE.RingGeometry(0.3, 0.42, 20);
    const impactMaterials = [0xffce8e, 0x9eeaff].map(
      (color) =>
        new THREE.MeshBasicMaterial({
          color,
          transparent: true,
          side: THREE.DoubleSide,
        }),
    );
    const impacts = new Map<number, THREE.Mesh>();
    const resize = () => {
      const w = Math.max(container.clientWidth, 1),
        h = Math.max(container.clientHeight, 1);
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.lookAt(0, 1.1, 0);
      camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    resize();
    const contextLost = (e: Event) => {
      e.preventDefault();
      setError(
        "Se perdió el contexto WebGL. Recarga para restaurar la vista 3D; puedes detener la batalla desde la cabecera.",
      );
    };
    renderer.domElement.addEventListener("webglcontextlost", contextLost);
    let animation = 0;
    const render = () => {
      const { previous, current, at } = frames.current;
      const alpha = Math.min(1, (performance.now() - at) / 50);
      const time = current.elapsed ?? 0;
      core.rotation.y = time * 0.25;
      const [left, right] = current.fighters ?? [];
      if (left && right) {
        const span = Math.abs(left.x - right.x) + 5;
        const distance = Math.max(
          12,
          span / (2 * Math.tan(THREE.MathUtils.degToRad(19)) * camera.aspect),
        );
        camera.position.x = THREE.MathUtils.lerp(
          camera.position.x,
          (left.x + right.x) / 2,
          0.08,
        );
        camera.position.z = THREE.MathUtils.lerp(
          camera.position.z,
          distance,
          0.08,
        );
        camera.lookAt(camera.position.x, 1.3, 0);
      }
      fighters.forEach((rig, i) => {
        const p = current.fighters?.[i];
        if (!p) return;
        const old =
          previous.round === current.round ? (previous.fighters?.[i] ?? p) : p;
        rig.root.position.set(
          THREE.MathUtils.lerp(old.x, p.x, alpha),
          THREE.MathUtils.lerp(old.y, p.y, alpha),
          0,
        );
        rig.root.rotation.y = p.facing > 0 ? Math.PI / 2 : -Math.PI / 2;
        const moving = p.action === "approach" || p.action === "retreat";
        const stride = moving
          ? Math.sin(time * 13) * 0.55
          : 0.06 * Math.sin(time * 3);
        rig.legs[0].rotation.x = stride;
        rig.legs[1].rotation.x = -stride;
        rig.arms[0].rotation.set(-0.25 - stride * 0.45, 0, -0.08);
        rig.arms[1].rotation.set(-0.45 + stride * 0.45, 0, 0.08);
        const recent = (current.effects ?? [])
          .filter(
            (e: any) =>
              e.kind === "cast" && e.player === p.id && time - e.at < 0.55,
          )
          .at(-1);
        if (p.action === "block") {
          rig.arms[0].rotation.x = -1.8;
          rig.arms[1].rotation.x = -1.8;
        }
        if (recent) {
          rig.arms[0].rotation.x = -1.55;
          rig.arms[1].rotation.x =
            recent.move === "projectile" || recent.move === "special"
              ? -1.55
              : -0.4;
          if (recent.move === "heavy") rig.legs[0].rotation.x = -1.3;
        }
        rig.root.rotation.z =
          p.health <= 0 ? p.facing * -1.1 : p.hurt > 0 ? p.facing * -0.13 : 0;
        rig.shield.visible = p.action === "block" && p.energy >= 5;
        rig.armor.emissive.setHex(p.hurt > 0 ? 0x993333 : 0x000000);
        rig.accent.emissiveIntensity = 0.35 + (p.energy / 100) * 0.5;
      });
      const activeIds = new Set<number>();
      for (const p of current.projectiles ?? []) {
        activeIds.add(p.id);
        let mesh = shots.get(p.id);
        if (!mesh) {
          mesh = new THREE.Mesh(shotGeometry, shotMaterials[p.owner]);
          scene.add(mesh);
          shots.set(p.id, mesh);
        }
        mesh.position.set(p.x, p.y, 0);
        mesh.rotation.set(time * 8, time * 11, 0);
        mesh.scale.setScalar(p.kind === "special" ? 2.1 : 1);
      }
      for (const [id, mesh] of shots)
        if (!activeIds.has(id)) {
          scene.remove(mesh);
          shots.delete(id);
        }
      const impactIds = new Set<number>();
      for (const effect of current.effects ?? []) {
        const age = time - effect.at;
        if (!["hit", "block"].includes(effect.kind) || age < 0 || age > 0.3)
          continue;
        impactIds.add(effect.id);
        let mesh = impacts.get(effect.id);
        const target = current.fighters?.find(
          (p: any) => p.id === effect.target,
        );
        if (!target) continue;
        if (!mesh) {
          mesh = new THREE.Mesh(
            impactGeometry,
            impactMaterials[effect.kind === "block" ? 1 : 0],
          );
          scene.add(mesh);
          impacts.set(effect.id, mesh);
        }
        mesh.position.set(target.x, target.y + 1.4, 0.5);
        mesh.scale.setScalar(0.5 + age * 5);
      }
      for (const [id, mesh] of impacts)
        if (!impactIds.has(id)) {
          scene.remove(mesh);
          impacts.delete(id);
        }
      renderer.render(scene, camera);
      animation = requestAnimationFrame(render);
    };
    animation = requestAnimationFrame(render);
    return () => {
      cancelAnimationFrame(animation);
      observer.disconnect();
      renderer.domElement.removeEventListener("webglcontextlost", contextLost);
      const geometries = new Set<THREE.BufferGeometry>(),
        materials = new Set<THREE.Material>();
      scene.traverse((object) => {
        const mesh = object as THREE.Mesh;
        if (mesh.geometry) geometries.add(mesh.geometry);
        if (mesh.material)
          (Array.isArray(mesh.material)
            ? mesh.material
            : [mesh.material]
          ).forEach((m) => materials.add(m));
      });
      geometries.add(shotGeometry);
      geometries.add(impactGeometry);
      impactMaterials.forEach((m) => materials.add(m));
      key.shadow.dispose();
      shotMaterials.forEach((m) => materials.add(m));
      geometries.forEach((g) => g.dispose());
      materials.forEach((m) => m.dispose());
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
    };
  }, []);
  const fighters = state.fighters ?? [];
  const lastRound = state.rounds?.at(-1);
  return (
    <section className="fighting-stage" aria-label="Arena de combate">
      <div ref={host} className="fighting-webgl" />
      <div className="fight-hud">
        {fighters.map((p: any, i: number) => (
          <div className={"fighter-status player-" + (i + 1)} key={p.id}>
            <div>
              <span>PLAYER {i + 1}</span>
              <b>{p.name}</b>
              <strong>{Math.ceil(p.health)} HP</strong>
            </div>
            <div className="fight-health">
              <i style={{ width: `${p.health}%` }} />
            </div>
            <div className="fight-energy">
              <i style={{ width: `${p.energy}%` }} />
            </div>
            <small>
              {Math.floor(p.energy)} energía ·{" "}
              {MOVE_NAMES[p.action] ?? p.action} · {state.wins?.[i] ?? 0} rondas
            </small>
          </div>
        ))}
      </div>
      <div className="fight-timer">
        <strong>{Math.ceil(state.timer ?? 0)}</strong>
        <small>
          RONDA {state.round} · BO{state.best_of}
        </small>
      </div>
      {state.phase !== "active" && (
        <div className="fight-announcement">
          <span>
            {state.phase === "intro"
              ? "PREPÁRATE"
              : state.phase === "finished"
                ? "FIN DEL COMBATE"
                : lastRound?.reason === "KO"
                  ? "K.O."
                  : "TIEMPO"}
          </span>
          <strong>
            {state.phase === "intro"
              ? `RONDA ${state.round}`
              : state.phase === "finished"
                ? state.winner
                  ? `${state.winner.toUpperCase()} GANA`
                  : "EMPATE"
                : lastRound?.winner
                  ? `${lastRound.winner.toUpperCase()} gana la ronda`
                  : "Ronda empatada"}
          </strong>
        </div>
      )}
      <div className="fight-caption">
        EMBER / FLUX{" "}
        <span>2.5D · PLANO XY · SIN MOVIMIENTO EN PROFUNDIDAD</span>
      </div>
      {error && (
        <div className="fight-webgl-error" role="alert">
          {error}
        </div>
      )}
    </section>
  );
}
