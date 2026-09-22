// Run: node --test tests/controls.unit.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { activeHold } from "../src/combat/useControls.ts";

test("releasing a tap key keeps the held guard", () => {
  const held = new Map([
    ["KeyS", "guard_high"],
    ["KeyJ", "light"],
  ]);
  held.delete("KeyJ");
  assert.equal(activeHold(held.values()), "guard_high");
});

test("latest hold wins, none left means neutral", () => {
  assert.equal(activeHold(["forward", "guard_high", "light"]), "guard_high");
  assert.equal(activeHold(["light", "jump"]), "");
});
