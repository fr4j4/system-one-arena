import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { createRig, type AnimationSource } from "./rig";

/** Isolated pose viewer: never creates matches or calls providers. */
export async function mountAnimationLab(host: HTMLElement) {
  host.innerHTML = `<main style="max-width:1200px;margin:32px auto;padding:0 24px">
    <a href="/">← Volver al combate</a><h1>Laboratorio de animaciones</h1>
    <p>Quaternius Standard · CC0 · Arrastra para girar la cámara. El visor no consulta modelos.</p>
    <div style="display:flex;gap:16px;flex-wrap:wrap;margin:20px 0">
      <label>Personaje <select id="character"><option>ember</option><option>flux</option><option>terra</option><option>nyx</option></select></label>
      <label>Animación <select id="clip"></select></label><button id="pause">Pausar</button>
      <label>Progreso <input id="progress" type="range" min="0" max="1" step="0.001" value="0"></label>
    </div>
    <div style="display:flex;justify-content:space-around"><b>Original</b><b>Quaternius / originales conservadas</b></div>
    <div id="viewport" style="height:560px;max-height:65vh;position:relative;border:1px solid #35394a;border-radius:12px;overflow:hidden"></div>
    <p id="status" role="status">Cargando personajes…</p>
    <p>10 clips importados: reposo, caminar, dos desplazamientos rápidos, salto, jab, cross, reacción, carga y proyectil. Los demás conservan la animación propia.</p>
    <a href="/">Probar combate con Quaternius</a> · <a href="/?animations=original">Probar combate original</a>
  </main>`;
  const get = <T extends HTMLElement>(id: string) =>
    host.querySelector<T>(`#${id}`)!;
  const viewport = get<HTMLDivElement>("viewport"),
    character = get<HTMLSelectElement>("character"),
    clip = get<HTMLSelectElement>("clip"),
    progress = get<HTMLInputElement>("progress"),
    pause = get<HTMLButtonElement>("pause"),
    status = get<HTMLParagraphElement>("status");
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
  viewport.append(renderer.domElement);
  renderer.domElement.setAttribute(
    "aria-label",
    "Comparación de personajes animados",
  );
  const scene = new THREE.Scene();
  scene.background = new THREE.Color("#141924");
  scene.add(new THREE.HemisphereLight(0xc1d8ff, 0x3a2832, 2.5));
  const key = new THREE.DirectionalLight(0xffe8d8, 3);
  key.position.set(3, 5, 5);
  scene.add(key);
  const grid = new THREE.GridHelper(14, 28, 0x58637b, 0x2c3549);
  scene.add(grid);
  const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 100);
  camera.position.set(0, 2.7, 9);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 1.15, 0);
  controls.update();
  const resize = new ResizeObserver(() => {
    const w = viewport.clientWidth,
      h = viewport.clientHeight;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  });
  resize.observe(viewport);
  let rigs: Awaited<ReturnType<typeof createRig>>[] = [],
    generation = 0,
    playing = true,
    phase = 0,
    seconds = 0;
  function describe() {
    status.textContent = rigs[1]?.importedNames.includes(clip.value)
      ? `${clip.value}: clip de Quaternius adaptado al rig original. Sin desplazamiento horizontal del root.`
      : `${clip.value}: animación original conservada en ambos personajes.`;
  }
  async function load() {
    const current = ++generation;
    character.disabled = true;
    status.textContent = "Cargando personajes…";
    try {
      const next = await Promise.all(
        (["original", "quaternius"] as AnimationSource[]).map((source) =>
          createRig(character.value, source),
        ),
      );
      if (current !== generation) {
        next.forEach((r) => r.dispose());
        return;
      }
      rigs.forEach((r) => {
        scene.remove(r.root);
        r.dispose();
      });
      rigs = next;
      rigs.forEach((r, i) => {
        r.root.position.x = i ? 1.6 : -1.6;
        scene.add(r.root);
      });
      const selected = clip.value;
      clip.replaceChildren(
        ...rigs[1].clipNames.map((name) => new Option(name, name)),
      );
      clip.value = selected || "idle";
      phase = 0;
      describe();
      host.dataset.ready = "true";
    } catch (error) {
      status.textContent = `No se pudieron cargar las animaciones: ${String(error)}`;
    } finally {
      if (current === generation) character.disabled = false;
    }
  }
  character.onchange = load;
  clip.onchange = () => {
    phase = 0;
    describe();
  };
  pause.onclick = () => {
    playing = !playing;
    pause.textContent = playing ? "Pausar" : "Reanudar";
  };
  progress.oninput = () => {
    playing = false;
    pause.textContent = "Reanudar";
    phase = Number(progress.value);
  };
  let last = performance.now(),
    frame = 0;
  function render(now: number) {
    const dt = Math.min(0.1, (now - last) / 1000);
    last = now;
    seconds += dt;
    if (playing && rigs.length)
      phase = (phase + dt / rigs[1].duration(clip.value)) % 1;
    progress.value = String(phase);
    rigs.forEach((r) => r.animate(clip.value, seconds, phase));
    renderer.render(scene, camera);
    frame = requestAnimationFrame(render);
  }
  frame = requestAnimationFrame(render);
  await load();
  window.addEventListener(
    "pagehide",
    () => {
      ++generation;
      cancelAnimationFrame(frame);
      resize.disconnect();
      controls.dispose();
      rigs.forEach((r) => r.dispose());
      grid.geometry.dispose();
      (grid.material as THREE.Material).dispose();
      renderer.dispose();
    },
    { once: true },
  );
}
