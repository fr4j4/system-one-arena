import * as THREE from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
export function createStage(scene: THREE.Scene, id: string, quality: string) {
  const reactor = id === "reactor";
  scene.background = new THREE.Color(reactor ? 0x0a1528 : 0x202538);
  scene.fog = new THREE.Fog(reactor ? 0x0a1528 : 0x333047, 28, 75);
  const ambient = new THREE.HemisphereLight(
    reactor ? 0xb8eaff : 0xffe3c6,
    0x283049,
    2.1,
  );
  scene.add(ambient);
  const sun = new THREE.DirectionalLight(reactor ? 0xc7eaff : 0xffd8ac, 3.5);
  sun.position.set(-5, 10, 7);
  sun.castShadow = quality !== "low";
  sun.shadow.mapSize.set(
    quality === "high" ? 2048 : 1024,
    quality === "high" ? 2048 : 1024,
  );
  Object.assign(sun.shadow.camera, {
    left: -13,
    right: 13,
    top: 8,
    bottom: -8,
    near: 0.1,
    far: 35,
  });
  sun.shadow.bias = -0.0005;
  scene.add(sun);
  const rim = new THREE.DirectionalLight(0x9a9bff, 2);
  rim.position.set(4, 4, -8);
  scene.add(rim);
  function mesh(
    g: THREE.BufferGeometry,
    m: THREE.Material,
    x: number,
    y: number,
    z: number,
  ) {
    const o = new THREE.Mesh(g, m);
    o.position.set(x, y, z);
    o.receiveShadow = true;
    scene.add(o);
    return o;
  }
  const stone = new THREE.MeshStandardMaterial({
    color: reactor ? 0x22354e : 0x665d69,
    roughness: 0.84,
    metalness: reactor ? 0.45 : 0.1,
  });
  const edge = new THREE.MeshStandardMaterial({
    color: reactor ? 0x111e34 : 0x383648,
    roughness: 0.6,
  });
  mesh(new THREE.BoxGeometry(23, 0.35, 7), stone, 0, -0.2, 0);
  mesh(new THREE.BoxGeometry(24, 0.25, 8), edge, 0, -0.5, 0);
  mesh(new THREE.BoxGeometry(22, 0.6, 6), edge, 0, -0.9, 0);
  const accent = new THREE.MeshBasicMaterial({
    color: reactor ? 0x66ceff : 0xc6a98c,
  });
  for (const z of [-3.05, 3.05])
    mesh(new THREE.BoxGeometry(22, 0.025, 0.055), accent, 0, 0.002, z);
  const line = new THREE.MeshStandardMaterial({
    color: reactor ? 0x38516b : 0x857981,
    roughness: 0.9,
  });
  for (let i = -10; i <= 10; i += 2) {
    mesh(new THREE.BoxGeometry(0.018, 0.01, 6), line, i, -0.015, 0);
  }
  for (let z = -2; z <= 2; z += 2)
    mesh(new THREE.BoxGeometry(22, 0.01, 0.018), line, 0, -0.015, z);
  const emblem = mesh(
    new THREE.TorusGeometry(2.7, 0.022, 5, 64),
    accent,
    0,
    0.01,
    0,
  );
  emblem.rotation.x = -Math.PI / 2;
  const animated: THREE.Object3D[] = [];
  if (reactor) {
    for (let i = 0; i < 3; i++) {
      const ring = mesh(
        new THREE.TorusGeometry(2.5 + i * 0.48, 0.045, 8, 96),
        new THREE.MeshBasicMaterial({ color: i === 1 ? 0x78b8d1 : 0x46667e }),
        0,
        3.7,
        -7 - i * 0.18,
      );
      ring.rotation.x = i * 0.25;
      animated.push(ring);
    }
    const core = mesh(
      new THREE.OctahedronGeometry(0.9, 0),
      new THREE.MeshStandardMaterial({
        color: 0x90d4ef,
        emissive: 0x39798d,
        emissiveIntensity: 0.8,
        metalness: 0.5,
        roughness: 0.2,
      }),
      0,
      3.7,
      -7,
    );
    animated.push(core);
    for (let i = 0; i < 12; i++) {
      const x = (i - 5.5) * 2.6;
      mesh(new THREE.BoxGeometry(0.55, 8, 0.6), edge, x, 3, -10);
      mesh(new THREE.BoxGeometry(0.045, 5, 0.05), accent, x, 3, -9.65);
    }
    for (let side of [-1, 1]) {
      const tower = mesh(
        new THREE.CylinderGeometry(0.8, 1, 7, 6),
        stone,
        side * 12,
        1.5,
        -5,
      );
      tower.rotation.y = 0.4;
      mesh(
        new THREE.TorusGeometry(0.85, 0.045, 6, 24),
        accent,
        side * 12,
        3.9,
        -5,
      ).rotation.x = Math.PI / 2;
    }
  } else {
    const moon = mesh(
      new THREE.SphereGeometry(2.25, 40, 24),
      new THREE.MeshBasicMaterial({ color: 0xe6b7a5 }),
      -5,
      7,
      -22,
    );
    mesh(
      new THREE.SphereGeometry(2.2, 40, 24),
      new THREE.MeshBasicMaterial({ color: 0x373246 }),
      -4.4,
      7.2,
      -20.9,
    );
    animated.push(moon);
    for (let layer = 0; layer < 3; layer++) {
      const material = new THREE.MeshStandardMaterial({
        color: [0x403e54, 0x343b50, 0x2c354b][layer],
        roughness: 1,
      });
      for (let i = 0; i < 10; i++) {
        const h = 4 + Math.sin(i * 2.71 + layer) * 3;
        const peak = mesh(
          new THREE.ConeGeometry(4 + layer, h + 4, 5),
          material,
          (i - 4.5) * 6,
          -1 + h * 0.3,
          -17 - layer * 9,
        );
        peak.rotation.y = i * 0.7;
      }
    }
    for (const side of [-1, 1]) {
      mesh(
        new THREE.CylinderGeometry(0.34, 0.52, 5.5, 8),
        stone,
        side * 8,
        2.3,
        -5,
      );
      mesh(new THREE.BoxGeometry(1.6, 0.28, 1.5), edge, side * 8, 5, -5);
      mesh(new THREE.BoxGeometry(1.1, 0.12, 1.15), accent, side * 8, 5.17, -5);
    }
    mesh(new THREE.BoxGeometry(17, 0.38, 0.8), edge, 0, 5.2, -5.2);
    for (let i = 0; i < 10; i++) {
      const island = mesh(
        new THREE.ConeGeometry(0.65 + Math.abs(Math.sin(i)), 1.7, 5),
        stone,
        (i - 4.5) * 3.6,
        2.8 + Math.sin(i * 2) * 2,
        -10 - (i % 3) * 2,
      );
      island.rotation.z = Math.PI;
      animated.push(island);
    }
  }
  const stars = new Float32Array(120 * 3);
  for (let i = 0; i < 120; i++) {
    stars[i * 3] = Math.sin(i * 12.9898) * 35;
    stars[i * 3 + 1] = 4 + (Math.sin(i * 7.2) + 1) * 9;
    stars[i * 3 + 2] = -15 - Math.abs(Math.cos(i * 3.8)) * 30;
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(stars, 3));
  scene.add(
    new THREE.Points(
      geometry,
      new THREE.PointsMaterial({
        color: reactor ? 0xaddfff : 0xf4d6c4,
        size: 0.055,
        transparent: true,
        opacity: 0.65,
      }),
    ),
  );
  // Batch static scenery by material; animated scenery keeps its own transforms.
  scene.updateMatrixWorld(true);
  const batches = new Map<THREE.Material, THREE.Mesh[]>();
  for (const child of [...scene.children]) {
    if (
      !(child instanceof THREE.Mesh) ||
      animated.includes(child) ||
      Array.isArray(child.material)
    )
      continue;
    const list = batches.get(child.material) ?? [];
    list.push(child);
    batches.set(child.material, list);
  }
  for (const [material, meshes] of batches) {
    if (meshes.length < 2) continue;
    const pieces = meshes.map((m) => {
      const g = m.geometry.index
        ? m.geometry.toNonIndexed()
        : m.geometry.clone();
      return g.applyMatrix4(m.matrixWorld);
    });
    const merged = mergeGeometries(pieces);
    pieces.forEach((g) => g.dispose());
    if (!merged) continue;
    const batch = new THREE.Mesh(merged, material);
    batch.receiveShadow = true;
    scene.add(batch);
    meshes.forEach((m) => {
      scene.remove(m);
      m.geometry.dispose();
    });
  }
  return {
    sun,
    animate(time: number) {
      for (let i = 0; i < animated.length; i++) {
        const o = animated[i];
        if (reactor) {
          o.rotation.z = time * (0.03 + i * 0.008);
          if (i === 3) o.rotation.y = time * 0.25;
        } else if (i > 0) o.rotation.y = time * 0.025 + i;
      }
    },
  };
}
