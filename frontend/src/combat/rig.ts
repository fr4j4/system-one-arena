import * as THREE from "three";
import { GLTFLoader, type GLTF } from "three/addons/loaders/GLTFLoader.js";
import { clone } from "three/addons/utils/SkeletonUtils.js";
const assets = new Map<string, Promise<GLTF>>();
export function preloadFighter(id: string) {
  let p = assets.get(id);
  if (!p) {
    p = new GLTFLoader().loadAsync(`/assets/combat/fighters/${id}.glb`);
    assets.set(id, p);
    p.catch(() => assets.delete(id));
  }
  return p;
}
export async function createRig(id: string) {
  const asset = await preloadFighter(id),
    model = clone(asset.scene),
    root = new THREE.Group();
  root.add(model);
  const ramp = new THREE.DataTexture(
    new Uint8Array([55, 105, 165, 220, 255]),
    5,
    1,
    THREE.RedFormat,
  );
  ramp.minFilter = ramp.magFilter = THREE.NearestFilter;
  ramp.needsUpdate = true;
  const materials: THREE.MeshToonMaterial[] = [];
  const outlineMat = new THREE.MeshBasicMaterial({
    color: 0x111623,
    side: THREE.BackSide,
  });
  const meshes: THREE.SkinnedMesh[] = [];
  model.traverse((object) => {
    if ((object as THREE.SkinnedMesh).isSkinnedMesh)
      meshes.push(object as THREE.SkinnedMesh);
  });
  for (const mesh of meshes) {
    const old = mesh.material as THREE.MeshStandardMaterial;
    const mat = new THREE.MeshToonMaterial({
      color: old.color,
      gradientMap: ramp,
      side: THREE.DoubleSide,
      emissive: old.emissive,
      emissiveIntensity: old.name === "energy" ? 0.3 : 0,
    });
    mat.name = old.name;
    mesh.material = mat;
    mesh.castShadow = mesh.receiveShadow = true;
    materials.push(mat);
    const outline = new THREE.SkinnedMesh(mesh.geometry, outlineMat);
    outline.bind(mesh.skeleton, mesh.bindMatrix);
    outline.scale.setScalar(1.012);
    outline.frustumCulled = false;
    mesh.parent?.add(outline);
  }
  const mixer = new THREE.AnimationMixer(model);
  const actions = new Map(
    asset.animations.map((clip) => [clip.name, mixer.clipAction(clip)]),
  );
  let active: THREE.AnimationAction | undefined;
  let activeName = "";
  let previous: THREE.AnimationAction | undefined;
  let blendStart = 0;
  return {
    root,
    model,
    materials,
    mixer,
    ramp,
    outlineMat,
    animate(name: string, seconds: number, progress?: number) {
      const action = actions.get(name) ?? actions.get("idle")!;
      if (name !== activeName) {
        previous?.stop();
        previous = active;
        blendStart = seconds;
        active = action;
        activeName = name;
        action
          .reset()
          .setEffectiveWeight(previous ? 0 : 1)
          .play();
      }
      if (previous) {
        const blend = Math.min(1, Math.max(0, (seconds - blendStart) / 0.075));
        previous.setEffectiveWeight(1 - blend);
        action.setEffectiveWeight(blend);
        if (blend === 1) {
          previous.stop();
          previous = undefined;
        }
      }
      const duration = action.getClip().duration;
      action.time =
        progress === undefined
          ? seconds % duration
          : Math.min(0.9999, Math.max(0, progress)) * duration;
      mixer.update(0);
    },
    dispose() {
      mixer.stopAllAction();
      mixer.uncacheRoot(model);
      ramp.dispose();
      outlineMat.dispose();
      materials.forEach((m) => m.dispose());
    },
  };
}
