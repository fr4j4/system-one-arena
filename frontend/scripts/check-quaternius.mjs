import fs from "node:fs";
import assert from "node:assert/strict";
import { AnimationClip, AnimationMixer, Vector3 } from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
const data = JSON.parse(
  fs.readFileSync(
    new URL(
      "../public/assets/combat/quaternius/animations.json",
      import.meta.url,
    ),
  ),
);
assert.equal(
  new Set(data.clips.map((c) => c.uuid)).size,
  data.clips.length,
  "Every clip needs a distinct mixer cache identity",
);
assert(
  data.clips.every((c) => typeof c.uuid === "string" && c.uuid.length === 36),
);
let samples = 0;
for (const id of ["ember", "flux", "terra", "nyx"]) {
  const b = fs.readFileSync(
    new URL(`../public/assets/combat/fighters/${id}.glb`, import.meta.url),
  );
  const { scene } = await new GLTFLoader().parseAsync(
    b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength),
    "",
  );
  const mixer = new AnimationMixer(scene);
  for (const json of data.clips) {
    const clip = AnimationClip.parse(json);
    assert(clip.validate(), clip.name);
    for (const track of clip.tracks) {
      assert(scene.getObjectByName(track.name.split(".")[0]), track.name);
      assert([...track.values].every(Number.isFinite));
    }
    const action = mixer.clipAction(clip).play();
    for (let i = 0; i < 11; i++) {
      mixer.setTime((i / 11) * clip.duration);
      scene.updateMatrixWorld(true);
      assert(
        scene.getObjectByName("Root").position.length() < 1e-6,
        "root motion",
      );
      const hip = scene.getObjectByName("Hips").position;
      assert(Math.abs(hip.x) < 1e-6 && Math.abs(hip.z) < 1e-6, "hip XZ drift");
      scene.traverse((n) => {
        if (n.isBone) {
          assert(Math.abs(n.quaternion.length() - 1) < 1e-5);
          assert(
            n.getWorldPosition(new Vector3()).length() < 4,
            `${clip.name}/${n.name}`,
          );
        }
      });
      samples++;
    }
    if (clip.name === "light" || clip.name === "heavy") {
      mixer.setTime(clip.duration * 0.3);
      scene.updateMatrixWorld(true);
      const hand = scene
        .getObjectByName(clip.name === "light" ? "HandR" : "HandL")
        .getWorldPosition(new Vector3());
      assert(
        hand.z > 0.65,
        `${id}/${clip.name}: punch must extend forward, got ${hand.z}`,
      );
    }
    action.stop();
  }
  mixer.stopAllAction();
}
console.log(
  `${samples} poses verified across four fighters: valid clips, normalized rotations, bounded skeletons, no root/XZ drift.`,
);
