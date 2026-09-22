"""Deterministic two-player combat on an XY plane. Rendering never owns physics."""

import copy

from arena.protocol import Question

MOVES = {
    "attack": {"cost": 8, "damage": 8, "range": 1.85, "windup": 0.12, "recovery": 0.32},
    "heavy": {"cost": 14, "damage": 16, "range": 2.25, "windup": 0.28, "recovery": 0.6},
    "projectile": {"cost": 25, "damage": 13, "range": 18, "windup": 0.32, "recovery": 0.75},
    "special": {"cost": 60, "damage": 30, "range": 18, "windup": 0.48, "recovery": 1.1},
}
DESCRIPTIONS = {
    "neutral": "Recover energy and stop moving",
    "approach": "Walk toward opponent",
    "retreat": "Walk away from opponent",
    "block": "Hold guard; reduces incoming damage to 25% while energy >= 5; costs 5 energy per hit",
    "jump": "Jump vertically to evade projectiles; costs 8 energy; movement remains on the XY plane",
    "attack": "Fast punch: range 1.85, 8 damage, 8 energy, 0.12s windup",
    "heavy": "Heavy kick: range 2.25, 16 damage, 14 energy, 0.28s windup",
    "projectile": "Energy bolt: 13 damage, 25 energy, 0.32s windup; can be blocked or jumped",
    "special": "Charged power wave: 30 damage, 60 energy, 0.48s windup; can be blocked or jumped",
}


class FightingWorld:
    def __init__(self, options=None):
        options = options or {}
        self.best_of = int(options.get("best_of", 3))
        if self.best_of not in (1, 3, 5):
            raise ValueError("best_of debe ser 1, 3 o 5")
        self.round_seconds = float(options.get("round_seconds", 45))
        if not 5 <= self.round_seconds <= 120:
            raise ValueError("La ronda debe durar entre 5 y 120 segundos")
        self.wins = [0, 0]
        self.round = 0
        self.history = []
        self.elapsed = 0.0
        self.done, self.outcome, self.winner = False, None, None
        self.score = 0
        self.events = []
        self.next_effect = 0
        self._new_round()

    def _new_round(self):
        self.round += 1
        self.timer = self.round_seconds
        self.phase, self.phase_time = "intro", 0.8
        self.projectiles = []
        self.fighters = [
            {
                "id": f"p{i + 1}",
                "name": name,
                "x": x,
                "y": 0.0,
                "z": 0.0,
                "vy": 0.0,
                "facing": 1 if i == 0 else -1,
                "health": 100.0,
                "energy": 100.0,
                "cooldown": 0.0,
                "stun": 0.0,
                "hurt": 0.0,
                "action": "neutral",
                "held": "neutral",
                "attack": None,
                "attack_phase": 0.0,
                "hits": 0,
                "damage": 0.0,
                "blocked": 0,
            }
            for i, (name, x) in enumerate((("Ember", -4.0), ("Flux", 4.0)))
        ]
        self._event("round_start", round=self.round)

    def _event(self, kind, **data):
        self.next_effect += 1
        self.events.append({"id": self.next_effect, "kind": kind, "at": self.elapsed, **data})
        self.events = self.events[-16:]

    def legal_actions(self, player=0):
        if self.done or self.phase != "active":
            return ["neutral"]
        p = self.fighters[player]
        actions = ["neutral", "approach", "retreat", "block"]
        if p["stun"] > 0 or p["attack"]:
            return ["neutral"]
        if p["y"] == 0 and p["energy"] >= 8:
            actions.append("jump")
        if p["cooldown"] <= 0:
            actions.extend(key for key, move in MOVES.items() if p["energy"] >= move["cost"])
        return actions

    def questions(self, player=0):
        return {
            "action": Question(
                type="choice",
                instructions=(
                    f"Control player {player + 1} ({self.fighters[player]['name']}) in a shared fighting arena. "
                    "Defeat the opponent and win rounds. Coordinates: x horizontal, y height, z always 0. "
                    "self and opponent are your perspective. Actions are discrete except walk/guard, which hold until refreshed or stale. "
                    "Respect energy, attack windup, cooldown, distance and incoming projectiles. No action executes outside active rounds."
                ),
                criteria={a: DESCRIPTIONS[a] for a in self.legal_actions(player)},
            )
        }

    def apply(self, action, player=0):
        if player not in (0, 1) or action not in self.legal_actions(player):
            return False
        p = self.fighters[player]
        if self.phase != "active":
            return action == "neutral"
        if action in MOVES:
            move = MOVES[action]
            p["energy"] -= move["cost"]
            p["held"] = "neutral"
            p["action"] = action
            p["attack"] = {"move": action, "remaining": move["windup"], "direction": p["facing"]}
            p["attack_phase"] = 0.0
            p["cooldown"] = move["windup"] + move["recovery"]
            self._event("cast", player=p["id"], move=action)
        elif action == "jump":
            p["energy"] -= 8
            p["vy"] = 7.5
            p["held"] = "neutral"
            p["action"] = "jump"
        else:
            p["held"] = action
            if not p["attack"] and p["stun"] <= 0:
                p["action"] = action
        return True

    def neutral(self, player=None):
        for i in range(2) if player is None else [player]:
            p = self.fighters[i]
            p["held"] = "neutral"
            if not p["attack"] and p["stun"] <= 0:
                p["action"] = "neutral"

    def tick(self, dt):
        if self.done:
            return
        self.elapsed += dt
        if self.phase != "active":
            self.phase_time -= dt
            if self.phase_time <= 0:
                if self.phase == "intro":
                    self.phase = "active"
                elif self.phase == "round_over":
                    self._new_round()
            return
        self.timer = max(0.0, self.timer - dt)
        hits = []
        for i, p in enumerate(self.fighters):
            enemy = self.fighters[1 - i]
            p["facing"] = 1 if enemy["x"] >= p["x"] else -1
            for key in ("cooldown", "stun", "hurt"):
                p[key] = max(0.0, p[key] - dt)
            p["energy"] = min(100.0, p["energy"] + 10 * dt)
            if p["y"] > 0 or p["vy"] > 0:
                p["vy"] -= 18 * dt
                p["y"] = max(0.0, p["y"] + p["vy"] * dt)
                if p["y"] == 0:
                    p["vy"] = 0.0
            if p["stun"] <= 0 and not p["attack"]:
                velocity = {"approach": 3.3, "retreat": -2.7}.get(p["held"], 0) * p["facing"]
                p["x"] = max(-8.0, min(8.0, p["x"] + velocity * dt))
                p["action"] = "jump" if p["y"] > 0.1 else p["held"]
            attack = p["attack"]
            if attack:
                move = MOVES[attack["move"]]
                attack["remaining"] -= dt
                p["attack_phase"] = min(1.0, 1 - attack["remaining"] / move["windup"])
                if attack["remaining"] <= 0:
                    name = attack["move"]
                    if name in ("projectile", "special"):
                        self.next_effect += 1
                        self.projectiles.append(
                            {
                                "id": self.next_effect,
                                "owner": i,
                                "x": p["x"] + attack["direction"] * 0.6,
                                "y": p["y"] + 1.0,
                                "z": 0.0,
                                "vx": attack["direction"] * (11 if name == "special" else 8),
                                "damage": move["damage"],
                                "kind": name,
                                "life": 3.0,
                            }
                        )
                    elif abs(p["x"] - enemy["x"]) <= move["range"] and abs(p["y"] - enemy["y"]) < 1.2:
                        hits.append((i, move["damage"], name))
                    p["attack"] = None
        # Body collision: stay on the combat plane; jumping permits crossing over an opponent.
        a, b = self.fighters
        if abs(a["x"] - b["x"]) < 0.85 and abs(a["y"] - b["y"]) < 1.1:
            middle = max(-7.55, min(7.55, (a["x"] + b["x"]) / 2))
            sign = 1 if b["x"] >= a["x"] else -1
            a["x"], b["x"] = middle - sign * 0.43, middle + sign * 0.43
        remaining = []
        for shot in self.projectiles:
            previous_x = shot["x"]
            shot["x"] += shot["vx"] * dt
            shot["life"] -= dt
            enemy = self.fighters[1 - shot["owner"]]
            crosses = min(previous_x, shot["x"]) - 0.5 <= enemy["x"] <= max(previous_x, shot["x"]) + 0.5
            if crosses and abs(shot["y"] - (enemy["y"] + 1)) < 0.9:
                hits.append((shot["owner"], shot["damage"], shot["kind"]))
            elif abs(shot["x"]) <= 10 and shot["life"] > 0:
                remaining.append(shot)
        self.projectiles = remaining
        # Resolve the frame's hits together, so simultaneous attacks can trade.
        for owner, damage, move in hits:
            source, target = self.fighters[owner], self.fighters[1 - owner]
            blocked = target["held"] == "block" and target["energy"] >= 5 and target["stun"] <= 0
            if blocked:
                damage *= 0.25
                target["energy"] -= 5
                target["blocked"] += 1
            else:
                target["stun"] = 0.18
                target["attack"] = None
                target["held"] = "neutral"
                target["action"] = "hurt"
            target["health"] = max(0.0, target["health"] - damage)
            target["hurt"] = 0.22
            source["hits"] += 1
            source["damage"] += damage
            self._event(
                "block" if blocked else "hit",
                player=source["id"],
                target=target["id"],
                damage=damage,
                move=move,
            )
        self.score = round(self.fighters[0]["damage"] - self.fighters[1]["damage"], 2)
        if self.timer <= 0 or min(p["health"] for p in self.fighters) <= 0:
            self._finish_round("timeout" if self.timer <= 0 else "KO")

    def _finish_round(self, reason):
        health = [round(p["health"], 3) for p in self.fighters]
        winner = None if health[0] == health[1] else 0 if health[0] > health[1] else 1
        if winner is not None:
            self.wins[winner] += 1
        self.history.append(
            {
                "round": self.round,
                "winner": None if winner is None else f"p{winner + 1}",
                "reason": reason,
                "health": health,
            }
        )
        self.neutral()
        self.projectiles = []
        self._event("round_end", **self.history[-1])
        if max(self.wins) >= self.best_of // 2 + 1 or self.round >= self.best_of + 2:
            self.done = True
            self.phase = "finished"
            self.winner = (
                None if self.wins[0] == self.wins[1] else "p1" if self.wins[0] > self.wins[1] else "p2"
            )
            self.outcome = "draw" if self.winner is None else "win" if self.winner == "p1" else "loss"
        else:
            self.phase, self.phase_time = "round_over", 2.0

    def observe(self):
        return {
            "scenario": "fighting",
            "version": 2,
            "fighters": copy.deepcopy(self.fighters),
            "projectiles": copy.deepcopy(self.projectiles),
            "round": self.round,
            "best_of": self.best_of,
            "timer": round(self.timer, 2),
            "phase": self.phase,
            "wins": self.wins[:],
            "rounds": copy.deepcopy(self.history),
            "effects": copy.deepcopy(self.events),
            "elapsed": round(self.elapsed, 3),
            "score": self.score,
            "done": self.done,
            "outcome": self.outcome,
            "winner": self.winner,
            "plane": "XY; z=0",
        }

    def perspective(self, player):
        # Public observations only: no pending opponent model response or future actions.
        fields = (
            "id",
            "name",
            "x",
            "y",
            "z",
            "health",
            "energy",
            "cooldown",
            "stun",
            "action",
            "attack",
            "facing",
        )

        def view(p):
            return {key: copy.deepcopy(p[key]) for key in fields}

        return {
            "scenario": "fighting",
            "player_id": f"p{player + 1}",
            "round": self.round,
            "phase": self.phase,
            "self": view(self.fighters[player]),
            "opponent": view(self.fighters[1 - player]),
            "projectiles": copy.deepcopy(self.projectiles),
            "wins": self.wins[:],
            "timer": round(self.timer, 2),
            "distance": round(abs(self.fighters[0]["x"] - self.fighters[1]["x"]), 3),
            "done": self.done,
        }


def fighting_reference(state, actions):
    if "self" not in state:
        fighters = state.get("fighters", [])
        if not fighters:
            return "neutral"
        state = {
            "self": fighters[0],
            "opponent": fighters[1],
            "distance": abs(fighters[0]["x"] - fighters[1]["x"]),
            "projectiles": state.get("projectiles", []),
        }
    me, enemy = state["self"], state["opponent"]
    if enemy.get("attack") and state["distance"] < 2.5:
        preferred = "block"
    elif any(
        abs(p["x"] - me["x"]) < 3 and p["owner"] != (0 if me["id"] == "p1" else 1)
        for p in state["projectiles"]
    ):
        preferred = "jump" if "jump" in actions else "block"
    elif state["distance"] > 3:
        preferred = "projectile" if "projectile" in actions else "approach"
    elif "special" in actions:
        preferred = "special"
    elif state["distance"] > 1.7:
        preferred = "approach"
    else:
        preferred = "heavy" if "heavy" in actions else "attack" if "attack" in actions else "block"
    return preferred if preferred in actions else "neutral"
