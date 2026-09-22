/** Offline retargeter. Run from frontend: node scripts/build-quaternius.mjs */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import {
  AnimationMixer,
  AnimationClip,
  QuaternionKeyframeTrack,
  VectorKeyframeTrack,
  Quaternion,
  Vector3,
  LoopOnce,
} from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);
const input = path.join(root, "assets/sources/quaternius/UAL1_Standard.glb");
async function load(p) {
  const b = fs.readFileSync(p);
  return new GLTFLoader().parseAsync(
    b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength),
    "",
  );
}
const source = await load(input),
  target = await load(
    path.join(root, "frontend/public/assets/combat/fighters/ember.glb"),
  );
source.scene.updateMatrixWorld(true);
target.scene.updateMatrixWorld(true);
// The original rig labels screen-left as L; UAL uses anatomical left (+X).
const names = {
  Hips: "pelvis",
  Spine: "spine_01",
  Chest: "spine_03",
  Neck: "neck_01",
  Head: "Head",
  ArmL: "upperarm_r",
  ForeL: "lowerarm_r",
  HandL: "hand_r",
  ArmR: "upperarm_l",
  ForeR: "lowerarm_l",
  HandR: "hand_l",
  ThighL: "thigh_r",
  ShinL: "calf_r",
  FootL: "foot_r",
  ThighR: "thigh_l",
  ShinR: "calf_l",
  FootR: "foot_l",
};
const endpoints = {
  ArmL: "ForeL",
  ForeL: "HandL",
  ArmR: "ForeR",
  ForeR: "HandR",
  ThighL: "ShinL",
  ShinL: "FootL",
  ThighR: "ShinR",
  ShinR: "FootR",
};
const pos = (n) => n.getWorldPosition(new Vector3());
const bindings = Object.entries(names).map(([name, src]) => {
  const s = source.scene.getObjectByName(src),
    t = target.scene.getObjectByName(name);
  if (!s || !t) throw Error(`Missing bone ${name}/${src}`);
  let correction = new Quaternion();
  const end =
    endpoints[name] ??
    (name === "HandL" ? "HandL" : name === "HandR" ? "HandR" : undefined);
  const start = name === "HandL" ? "ForeL" : name === "HandR" ? "ForeR" : name;
  if (end) {
    const td = pos(target.scene.getObjectByName(end))
      .sub(pos(target.scene.getObjectByName(start)))
      .normalize();
    const sd = pos(source.scene.getObjectByName(names[end]))
      .sub(pos(source.scene.getObjectByName(names[start])))
      .normalize();
    correction.setFromUnitVectors(td, sd);
  }
  return {
    name,
    s,
    t,
    restInverse: s.getWorldQuaternion(new Quaternion()).invert(),
    correction,
  };
});
const sourceHip = pos(source.scene.getObjectByName("pelvis")).y;
const targetHip = target.scene.getObjectByName("Hips").position.clone();
const legScale =
  (pos(target.scene.getObjectByName("Hips")).y -
    pos(target.scene.getObjectByName("FootL")).y) /
  (sourceHip - pos(source.scene.getObjectByName("foot_r")).y);
const mapping = {
  idle: "Idle_Loop",
  walk: "Walk_Loop",
  dash_forward: "Jog_Fwd_Loop",
  dash_back: "Jog_Fwd_Loop",
  jump: "Jump_Loop",
  light: "Punch_Jab",
  heavy: "Punch_Cross",
  hurt: "Hit_Chest",
  charge: "Spell_Simple_Idle_Loop",
  bolt: "Spell_Simple_Shoot",
};
const clips = [];
for (const [name, sourceName] of Object.entries(mapping)) {
  const clip = source.animations.find((c) => c.name === sourceName);
  if (!clip) throw Error(sourceName);
  const mixer = new AnimationMixer(source.scene),
    action = mixer.clipAction(clip);
  action.setLoop(LoopOnce, 1);
  action.clampWhenFinished = true;
  action.play();
  const count = Math.ceil(clip.duration * 30),
    times = [],
    values = Object.fromEntries(bindings.map((b) => [b.name, []])),
    hips = [];
  for (let i = 0; i <= count; i++) {
    const time = (i / count) * clip.duration;
    times.push(time);
    mixer.setTime(time);
    source.scene.updateMatrixWorld(true);
    const world = { Root: new Quaternion() };
    for (const b of bindings)
      world[b.name] = b.s
        .getWorldQuaternion(new Quaternion())
        .multiply(b.restInverse)
        .multiply(b.correction)
        .normalize();
    for (const b of bindings) {
      const q = (world[b.t.parent.name] ?? new Quaternion())
        .clone()
        .invert()
        .multiply(world[b.name])
        .normalize();
      const v = values[b.name];
      if (v.length && q.dot(new Quaternion().fromArray(v, v.length - 4)) < 0)
        q.set(-q.x, -q.y, -q.z, -q.w);
      v.push(...q.toArray());
    }
    // Only local hip bob is imported. Root X/Z and jump height remain server-owned.
    const y =
      name === "jump"
        ? targetHip.y
        : targetHip.y +
          (pos(source.scene.getObjectByName("pelvis")).y - sourceHip) *
            legScale;
    hips.push(targetHip.x, y, targetHip.z);
  }
  const tracks = bindings.map(
    (b) =>
      new QuaternionKeyframeTrack(
        `${b.name}.quaternion`,
        times,
        values[b.name],
      ),
  );
  tracks.push(new VectorKeyframeTrack("Hips.position", times, hips));
  clips.push(
    AnimationClip.toJSON(new AnimationClip(name, clip.duration, tracks)),
  );
  mixer.stopAllAction();
  mixer.uncacheRoot(source.scene);
}
// AnimationMixer keys actions by clip UUID. Keep distinct, deterministic identities.
clips.forEach((c) => {
  const hex = createHash("sha256")
    .update(`quaternius-standard-v1:${c.name}`)
    .digest("hex")
    .slice(0, 32);
  c.uuid = `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
});
const result = {
  version: 1,
  source: "Quaternius Universal Animation Library Standard",
  url: "https://quaternius.itch.io/universal-animation-library",
  license: "CC0-1.0",
  sha256: createHash("sha256").update(fs.readFileSync(input)).digest("hex"),
  fps: 30,
  mapping,
  clips,
};
const out = path.join(root, "frontend/public/assets/combat/quaternius");
fs.mkdirSync(out, { recursive: true });
fs.writeFileSync(path.join(out, "animations.json"), JSON.stringify(result));
console.log(`Retargeted ${clips.length} clips → ${out}/animations.json`);
