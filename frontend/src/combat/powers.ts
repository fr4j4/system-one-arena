import * as THREE from "three";
import type { Frame } from "./types";
const colors: Record<string, number> = {
  ember: 0xff8b51,
  flux: 0x69dcff,
  terra: 0xf3c77c,
  nyx: 0xc0a1ff,
};
/** Original character-specific VFX, driven exclusively by the authoritative phase. */
export function createPowers(scene: THREE.Scene, characters: string[]) {
  const groups = characters.map((character) => {
    const root = new THREE.Group();
    scene.add(root);
    const material = new THREE.MeshBasicMaterial({
      color: colors[character],
      transparent: true,
      opacity: 0.68,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    const meshes: THREE.Mesh[] = [];
    const count = character === "ember" ? 10 : character === "terra" ? 7 : 12;
    for (let i = 0; i < count; i++) {
      const geometry =
        character === "ember"
          ? new THREE.ConeGeometry(0.18, 1.6, 4)
          : character === "terra"
            ? new THREE.CylinderGeometry(0.15, 0.42, 2.8, 5)
            : character === "flux"
              ? new THREE.CylinderGeometry(0.025, 0.065, 1.15, 4)
              : new THREE.OctahedronGeometry(0.16, 0);
      const m = new THREE.Mesh(geometry, material);
      root.add(m);
      meshes.push(m);
    }
    const halo = new THREE.Mesh(
      new THREE.TorusGeometry(1, 0.03, 5, 64),
      material,
    );
    root.add(halo);
    return { root, material, meshes, halo, character };
  });
  return {
    update(frame: Frame, time: number, reduced: boolean) {
      groups.forEach((g, i) => {
        const fighter = frame.fighters[i],
          opponent = frame.fighters[1 - i];
        const final = frame.phase === "finisher" && frame.winner === fighter.id;
        const ultimate =
          frame.phase === "cinematic" &&
          frame.cinematic?.player_id === fighter.id;
        const signature = fighter.move === "signature";
        g.root.visible = final || ultimate || signature;
        if (!g.root.visible) return;
        const progress = final
          ? 1 - frame.phase_left / 300
          : ultimate
            ? 1 - frame.phase_left / 90
            : Math.min(1, fighter.age / 45);
        const envelope = Math.max(0.08, Math.sin(Math.PI * progress));
        g.root.position.set(final || ultimate ? opponent.x : fighter.x, 0, 0);
        g.root.scale.setScalar(
          (final ? 1.7 : ultimate ? 1.25 : 0.62) * envelope,
        );
        g.material.opacity = reduced ? 0.25 : 0.65;
        const spin = reduced ? 0 : time;
        g.meshes.forEach((m, j) => {
          const a = (j / g.meshes.length) * Math.PI * 2;
          if (g.character === "ember") {
            const side = j % 2 === 0 ? 1 : -1,
              rank = Math.floor(j / 2);
            m.position.set(
              side * (0.4 + rank * 0.24),
              1.3 + rank * 0.14,
              Math.sin(rank) * 0.15,
            );
            m.rotation.z = side * (-0.35 - rank * 0.16);
            m.scale.set(1, 1 + rank * 0.12, 1);
          } else if (g.character === "terra") {
            m.position.set(
              Math.cos(a) * 1.1,
              Math.max(-1, progress * 4 - 1.2),
              Math.sin(a) * 0.7,
            );
            m.rotation.z = Math.cos(a) * -0.15;
          } else if (g.character === "flux") {
            m.position.set(
              Math.cos(a + spin * 4) * 0.9,
              0.5 + (j % 4) * 0.52,
              Math.sin(a + spin * 4) * 0.7,
            );
            m.rotation.z = Math.sin(a + spin * 8) * 1.2;
          } else {
            m.position.set(
              Math.cos(a + spin) * 1.1,
              1.35 + Math.sin(a + spin) * 0.95,
              Math.sin(a * 2 + spin) * 0.65,
            );
            m.rotation.set(spin + j, spin * 2, 0);
            m.scale.setScalar(1.2 + progress);
          }
        });
        g.halo.position.y = 1.3;
        g.halo.rotation.set(
          g.character === "terra" ? Math.PI / 2 : 0,
          0,
          spin * 0.4,
        );
        g.halo.scale.setScalar(g.character === "nyx" ? 1.25 : 1.7);
      });
    },
  };
}
