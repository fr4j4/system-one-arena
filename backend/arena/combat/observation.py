"""Only observable tactical information crosses the model boundary."""

import hashlib

from arena.protocol import Question

from .content import MOVES, ROUTES, SIGNATURES

INSTRUCTIONS = "Choose the best action to win this 2D fight. Check distance and attack reach before striking: melee cannot hit distant enemies. Move closer or use ranged powers. Energy is limited; charge restores it. Block incoming attacks. High guard loses to low; low guard loses to overhead; throws beat guards. Timing is frames at 60fps. Clash: simultaneous hold/push/surge cost0/10/20, strength1/2/4; repeated surge2."


def describe(action, fighter):
    if action in MOVES or action == "signature":
        move = SIGNATURES[fighter] if action == "signature" else MOVES[action]
        return f"{action.replace('_', ' ')}: reach {move['range'] / 1000:g}m, cost {move['energy']}"
    return {
        "forward": "approach enemy",
        "back": "retreat",
        "charge": "recover energy, vulnerable",
        "dash_forward": "quick approach 1.8m",
        "dash_back": "quick retreat 1.8m",
        "evade": "dodge cost20",
        "combo_pressure": "light-light-heavy reach1.2m",
        "combo_air": "light-launcher-air reach1.2m cost10",
        "combo_power": "light-heavy-signature reach1.2m cost25",
        "combo_chase": "dash-light-bolt reach3m cost15",
    }.get(action, action.replace("_", " "))


def observe(world, i):
    snap = world.snapshot()
    f = snap["fighters"][i]
    enemy = snap["fighters"][1 - i]
    actions = world.legal(i)

    def view(p):
        return dict(
            character=p["character"],
            x=round(p["x"], 2),
            y=round(p["y"], 2),
            hp=p["health"],
            energy=round(p["energy"], 1),
            guard=round(p["guard"], 1),
            facing=p["facing"],
            action=p["action"],
            move=p["move"],
            frame=p["age"] if p["move"] else 0,
            stun=p["stun"],
            invulnerable=p["invulnerable"],
            combo=p["combo_hits"],
        )

    state = dict(
        scenario="combat",
        seed=world.config.get("seed", 42),
        practice=world.config.get("preset") if world.config.get("mode") == "training" else None,
        player_id=f["id"],
        phase=world.phase,
        round=world.round,
        time=round(snap["timer"], 1),
        wins=world.wins[:],
        self=view(f),
        opponent=view(enemy),
        distance=round(abs(f["x"] - enemy["x"]), 2),
        walls=[-10, 10],
        projectiles=[
            [p["owner"], p["kind"], round(p["x"], 2), round(p["y"], 2), p["direction"]]
            for p in snap["projectiles"]
        ],
        moves=[],
        recent=[
            {k: e[k] for k in ("kind", "player_id", "move", "damage") if k in e}
            for e in world.events
            if e["kind"] in ("hit", "block", "parry", "escape")
        ][-4:],
    )
    for action in actions:
        if action in MOVES or action == "signature":
            spec = SIGNATURES[f["character"]] if action == "signature" else MOVES[action]
            state["moves"].append(
                [action, spec["energy"], spec["damage"], spec["startup"], spec["range"] / 1000]
            )
        elif action in ROUTES:
            state["moves"].append([action, ROUTES[action]["energy"], "-".join(ROUTES[action]["steps"])])
    if world.phase == "clash":
        state["clash"] = {k: snap["clash"][k] for k in ("pulse", "score", "history")}
    return dict(
        state=state,
        actions=actions,
        questions={
            "action": Question(
                type="choice",
                instructions=INSTRUCTIONS,
                criteria={a: describe(a, f["character"]) for a in actions},
            ).model_dump()
        }
        if actions
        else {},
    )


def reference(state, actions, style="reference"):
    if not actions:
        return "neutral"
    if style == "dummy":
        if state.get("practice") == "defense" and "guard_high" in actions:
            return "guard_high"
        return "neutral" if "neutral" in actions else actions[0]
    if state["phase"] == "finish":
        return "finish"
    if state["phase"] == "clash":
        history = state.get("clash", {}).get("history", [])
        index = 0 if state["player_id"] == "p1" else 1
        repeat = bool(history and history[-1]["choices"][index]["action"] == "surge")
        return next(
            (a for a in (["push", "surge", "hold"] if repeat else ["surge", "push", "hold"]) if a in actions),
            actions[0],
        )
    me, enemy = state["self"], state["opponent"]
    distance = state["distance"]
    if "break" in actions:
        return "break"
    if style == "defensive":
        preferred = "guard_low" if enemy["action"] == "low" else "guard_high"
    elif me["y"] > 0:
        preferred = "air_heavy"
    elif style == "aggressive":
        preferred = "combo_pressure" if distance < 1.2 else "dash_forward" if distance > 2 else "heavy"
    elif enemy["move"] in ("beam", "bolt", "ultimate") and enemy["frame"] < 25:
        preferred = "jump_forward" if distance > 2 else "evade"
    elif enemy["move"] and distance < 2.3:
        preferred = "guard_low" if enemy["move"] == "low" else "guard_high"
    elif me["energy"] >= 100 and distance < 2.4:
        preferred = "ultimate"
    elif enemy["action"].startswith("guard") and distance < 0.9:
        preferred = "throw"
    elif distance < 1.2:  # combo reach; wider just whiffs in place
        preferred = (
            "combo_air"
            if me["energy"] >= 10 and me["hp"] < 600
            else "combo_power"
            if me["energy"] >= 25
            else "combo_pressure"
        )
    elif distance < 2:
        preferred = "signature" if me["energy"] >= 25 else "forward"
    elif me["energy"] < 35 and distance > 4:
        preferred = "charge"
    elif me["energy"] >= 35 and distance > 4:
        # Seeded per-player coin (25%): a reference mirror otherwise beams in lockstep into a
        # zero-energy clash that always ties, and the round times out untouched.
        key = f"{state.get('seed')}:{state['player_id']}:{state['round']}:{state['time']}"
        preferred = "dash_forward" if hashlib.sha256(key.encode()).digest()[0] < 64 else "beam"
    elif distance > 3:
        preferred = "combo_chase"
    else:
        preferred = "forward"
    return preferred if preferred in actions else "forward" if "forward" in actions else actions[0]
