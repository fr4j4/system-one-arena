"""Integer fixed-step fighting world. All times are ticks, positions millimetres,
energy/guard centipoints. No clocks, IO, inference or renderer dependencies."""

import copy
from dataclasses import asdict, dataclass, field

from .content import CONTENT_VERSION, FIGHTERS, MOVES, ROUTES, RULES_VERSION, SIGNATURES


@dataclass
class Fighter:
    id: str
    character: str
    x: int
    facing: int
    y: int = 0
    vy: int = 0
    health: int = 1000
    energy: int = 2500
    guard: int = 10000
    action: str = "neutral"
    held: str = "neutral"
    hold_until: int = 0
    guard_started: int = -100
    parry_ready: int = 0
    guard_quiet: int = 0
    move: str | None = None
    age: int = 0
    connected: bool = False
    contacts: list = field(default_factory=list)
    stun: int = 0
    knockdown: int = 0
    invulnerable: int = 0
    dash_ready: int = 0
    evade_ready: int = 0
    dash_left: int = 0
    dash_direction: int = 0
    route: list = field(default_factory=list)
    route_name: str | None = None
    request_id: str | None = None
    source: str = "engine"
    combo_hits: int = 0
    air_hits: int = 0
    combo_from: int = -1
    combo_break_used: bool = False
    hurt_until: int = 0
    armor_used: bool = False
    stats: dict = field(
        default_factory=lambda: dict(
            damage=0,
            received=0,
            hits=0,
            blocks=0,
            parries=0,
            guard_breaks=0,
            whiffs=0,
            energy_spent=0,
            energy_gained=0,
            combos=0,
            escapes=0,
            ultimates=0,
            clashes=0,
        )
    )


class World:
    def __init__(self, config):
        self.config = copy.deepcopy(config)
        self.tick = 0
        self.epoch = 0
        self.round = 0
        self.wins = [0, 0]
        self.history = []
        self.events = []
        self.event_seq = 0
        self.projectile_seq = 0
        self.projectiles = []
        self.phase = "intro"
        self.phase_left = 60
        self.hitstop = 0
        self.winner = None
        self.done = False
        self.clash = None
        self.cinematic = None
        self.fighters = []
        self.new_round()

    def event(self, kind, **data):
        self.event_seq += 1
        self.events.append(dict(seq=self.event_seq, tick=self.tick, round=self.round, kind=kind, **data))
        self.events = self.events[-100:]

    def new_round(self):
        previous = [f.stats for f in self.fighters]
        self.round += 1
        self.epoch += 1
        self.timer = self.config.get("round_seconds", 90) * 60
        self.phase, self.phase_left = "intro", 60
        self.projectiles = []
        self.clash = self.cinematic = None
        self.hitstop = 0
        self.fighters = [
            Fighter(f"p{i + 1}", slot["fighter_id"], -4000 if i == 0 else 4000, 1 if i == 0 else -1)
            for i, slot in enumerate(self.config["players"])
        ]
        for i, f in enumerate(self.fighters):
            if previous:
                f.stats = previous[i]
        if self.config.get("mode") == "training":
            self.setup(self.config.get("preset", "neutral"))
        self.event("round_start")

    def setup(self, preset):
        a, b = self.fighters
        if preset in ("close", "defense", "air"):
            a.x, b.x = -650, 650
        if preset in ("clash", "ultimate"):
            a.energy = b.energy = 10000
        if preset == "ultimate":
            a.x, b.x = -1000, 1000
        if preset == "corner":
            a.x, b.x = -9200, -7600
        if preset == "air":
            a.y = b.y = 1800
        if preset == "defense":
            b.held = "guard_high"
            b.hold_until = self.tick + 36000

    def definition(self, f, name=None):
        name = name or f.move
        return SIGNATURES[f.character] if name == "signature" else MOVES[name]

    def legal(self, i):
        f = self.fighters[i]
        if self.done:
            return []
        if self.phase == "finish":
            return ["finish", "spare"] if self.winner == f.id else []
        if self.phase == "clash":
            if f.id in self.clash["choices"]:
                return []
            return (
                ["hold", "yield"]
                + (["push"] if f.energy >= 1000 else [])
                + (["surge"] if f.energy >= 2000 else [])
            )
        if self.phase != "active":
            return []
        if f.stun or f.knockdown:
            return (
                ["break"]
                if f.energy >= 5000 and not f.combo_break_used and f.combo_from >= 0 and f.action != "thrown"
                else []
            )
        if self.hitstop:
            return []
        if f.move or f.dash_left:
            return []
        if f.y > 0:
            return ["neutral", "air_heavy"]
        result = [
            "neutral",
            "forward",
            "back",
            "crouch",
            "jump",
            "jump_forward",
            "jump_back",
            "guard_high",
            "guard_low",
            "light",
            "heavy",
            "low",
            "overhead",
            "throw",
        ]
        if f.energy < 10000:
            result.append("charge")
        if self.tick >= f.dash_ready:
            result += ["dash_forward", "dash_back"]
        if f.energy >= 2000 and self.tick >= f.evade_ready:
            result.append("evade")
        for name in ("launcher", "bolt", "beam", "signature", "ultimate"):
            if f.energy >= self.definition(f, name)["energy"] * 100 and (
                name not in ("bolt", "beam") or sum(p["owner"] == i for p in self.projectiles) < 3
            ):
                result.append(name)
        result.extend(
            k
            for k, v in ROUTES.items()
            if f.energy >= v["energy"] * 100 and (k != "combo_chase" or self.tick >= f.dash_ready)
        )
        return result

    def gain(self, f, n):
        actual = min(n, 10000 - f.energy)
        f.energy += actual
        f.stats["energy_gained"] += actual / 100

    def spend(self, f, n):
        if f.energy < n * 100:
            return False
        f.energy -= n * 100
        f.stats["energy_spent"] += n
        return True

    def apply(self, i, action, source="model", request_id=None):
        if i not in (0, 1) or action not in self.legal(i):
            return False
        f = self.fighters[i]
        if self.phase == "clash":
            self.clash["choices"][f.id] = dict(action=action, source=source, request_id=request_id)
            return True
        f.source, f.request_id = source, request_id
        if self.phase == "finish":
            self.event("finisher_choice", player_id=f.id, action=action, source=source, request_id=request_id)
            if action == "finish":
                self.phase = "finisher"
                self.phase_left = 300
                self.epoch += 1
            else:
                self.finish()
            return True
        self.event("command", player_id=f.id, action=action, source=source, request_id=request_id)
        if action in ROUTES:
            f.route = ROUTES[action]["steps"][:]
            f.route_name = action
            f.stats["combos"] += 1
            self.start(f, f.route.pop(0))
        elif action in MOVES or action == "signature":
            self.start(f, action)
        elif action == "break":
            self.spend(f, 50)
            f.stun = f.knockdown = 0
            f.invulnerable = 20
            f.combo_break_used = True
            f.combo_from = -1
            enemy = self.fighters[1 - i]
            enemy.stun = 24
            enemy.move = None
            enemy.route = []
            enemy.held = "neutral"
            enemy.x = max(-9500, min(9500, enemy.x + f.facing * 1800))
            f.stats["escapes"] += 1
            self.event("escape", player_id=f.id)
        elif action in ("dash_forward", "dash_back", "evade"):
            self.start(f, action)
        elif action.startswith("jump"):
            f.vy = 170
            f.held = "forward" if action == "jump_forward" else "back" if action == "jump_back" else "neutral"
            f.hold_until = self.tick + 42
            f.action = "jump"
        else:
            if action.startswith("guard") and not f.held.startswith("guard"):
                f.guard_started = self.tick if self.tick >= f.parry_ready else -100
                f.parry_ready = self.tick + 30
            if action == "charge" and f.held != "charge":
                f.age = 0
            f.held = f.action = action
            f.hold_until = self.tick + ({"charge": 48, "guard_high": 36, "guard_low": 36}.get(action, 24))
        return True

    def start(self, f, name):
        if name in ("dash_forward", "dash_back", "evade"):
            if name == "evade":
                if not self.spend(f, 20):
                    return False
                f.invulnerable = 8
                f.evade_ready = self.tick + 90
            f.dash_direction = f.facing * (-1 if name in ("dash_back", "evade") else 1)
            f.dash_left = 12
            f.dash_ready = self.tick + 30
            f.held = "neutral"
            f.action = name
            return True
        spec = self.definition(f, name)
        if not self.spend(f, spec["energy"]):
            f.route = []
            f.route_name = None
            return False
        f.move = f.action = name
        f.age = 0
        f.connected = False
        f.contacts = []
        f.held = "neutral"
        f.armor_used = False
        if name == "air_heavy" and f.y == 0 and f.route_name:
            f.vy = 220
        if name == "signature" and f.character == "flux":
            f.dash_left = 12
            f.dash_direction = f.facing
        self.event(
            "move_start",
            player_id=f.id,
            move=name,
            source=f.source if not f.route_name else "route",
            request_id=f.request_id,
            route=f.route_name,
        )
        if name == "ultimate":
            f.stats["ultimates"] += 1
        return True

    def neutral(self, i=None):
        for f in self.fighters if i is None else [self.fighters[i]]:
            f.held = "neutral"
            f.hold_until = 0
            if not f.move and not f.stun:
                f.action = "neutral"

    def step(self):
        if self.done:
            return
        self.tick += 1
        if self.phase == "clash":
            self.step_clash()
            return
        if self.phase in ("intro", "round_over", "cinematic", "finish", "finisher"):
            self.phase_left -= 1
            if self.phase_left <= 0:
                if self.phase == "round_over":
                    self.new_round()
                elif self.phase in ("finish", "finisher"):
                    self.finish()
                else:
                    was_intro = self.phase == "intro"
                    self.phase = "active"
                    self.epoch += 1
                    self.cinematic = None
                    if was_intro and self.config.get("mode") == "training":
                        if self.config.get("preset") == "clash":
                            self.begin_clash()
                        elif self.config.get("preset") == "finisher":
                            self.fighters[1].health = 0
                            self.winner = "p1"
                            self.phase, self.phase_left = "finish", 180
            return
        if self.hitstop:
            self.hitstop -= 1
            return
        if self.config.get("mode") != "training":
            self.timer = max(0, self.timer - 1)
        hits = []
        for i, f in enumerate(self.fighters):
            enemy = self.fighters[1 - i]
            if not f.move:
                f.facing = 1 if enemy.x >= f.x else -1
            f.invulnerable = max(0, f.invulnerable - 1)
            f.stun = max(0, f.stun - 1)
            if f.knockdown:
                f.knockdown -= 1
                if not f.knockdown:
                    f.invulnerable = 30
            if not f.stun and not f.knockdown and f.guard <= 0:
                f.guard = 5000
            if f.y or f.vy:
                f.vy -= 8
                f.y = max(0, f.y + f.vy)
                if f.y == 0:
                    f.vy = 0
            if f.combo_from >= 0 and not f.stun and not f.knockdown and f.y == 0:
                f.combo_from = -1
                f.combo_hits = f.air_hits = 0
                f.combo_break_used = False
            if self.tick > f.hold_until:
                f.held = "neutral"
            if not f.stun and not f.knockdown:
                if f.dash_left:
                    f.x += 150 * f.dash_direction
                    f.dash_left -= 1
                    if not f.dash_left and f.route and not f.move:
                        self.start(f, f.route.pop(0))
                elif not f.move:
                    f.x += {"forward": 75, "back": -60}.get(f.held, 0) * f.facing
                    f.action = "jump" if f.y else f.held
                    if f.held == "charge":
                        f.age += 1
                        if f.age > 15:
                            self.gain(f, 20)
                    elif self.tick % 3 == 0 and f.held in ("neutral", "forward", "back"):
                        self.gain(f, 10)
                if f.held.startswith("guard"):
                    f.guard_quiet = self.tick
                elif self.tick - f.guard_quiet >= 60 and self.tick % 3 == 0:
                    f.guard = min(10000, f.guard + 100)
            f.x = max(-9500, min(9500, f.x))
            if not f.move:
                continue
            f.age += 1
            spec = self.definition(f)
            active = spec["startup"] <= f.age < spec["startup"] + spec["active"]
            if active:
                offset = f.age - spec["startup"]
                if f.move in ("bolt", "beam") and offset == 0:
                    self.projectile_seq += 1
                    self.projectiles.append(
                        dict(
                            id=self.projectile_seq,
                            owner=i,
                            kind=f.move,
                            x=f.x + f.facing * 500,
                            y=f.y + 1000,
                            origin=f.x,
                            direction=f.facing,
                            vx=f.facing * (500 if f.move == "beam" else 170),
                            life=120 if f.move == "bolt" else 60,
                            damage=spec["damage"],
                            request_id=f.request_id,
                        )
                    )
                    f.connected = True
                elif not spec.get("counter") and f.move not in ("bolt", "beam"):
                    contact = offset // 5 if spec.get("multi") else 0
                    if (
                        contact not in f.contacts
                        and abs(f.x - enemy.x) <= spec["range"]
                        and abs(f.y - enemy.y) < 1200
                        and (f.move != "throw" or (not f.y and not enemy.y))
                    ):
                        f.contacts.append(contact)
                        hits.append((i, f.move, spec.copy(), contact))
            if f.age >= spec["startup"] + spec["active"]:
                if f.route and f.connected:
                    self.start(f, f.route.pop(0))
                elif f.age >= spec["startup"] + spec["active"] + spec["recovery"]:
                    if not f.connected:
                        f.stats["whiffs"] += 1
                    f.move = None
                    f.route = []
                    f.route_name = None
                    f.action = "neutral"
        self.bodies()
        if self.projectile_step(hits):
            return
        ultimate = None
        for i, name, spec, contact in hits:
            if self.hit(i, name, spec, contact) and name == "ultimate":
                ultimate = i
        if self.config.get("mode") != "training" and (
            self.timer <= 0 or min(f.health for f in self.fighters) <= 0
        ):
            self.end_round()
        elif ultimate is not None:
            self.phase = "cinematic"
            self.phase_left = 90
            self.epoch += 1
            self.cinematic = dict(kind="ultimate", player_id=f"p{ultimate + 1}")
            self.neutral()
        elif self.config.get("mode") == "training" and min(f.health for f in self.fighters) <= 0:
            self.phase = "round_over"
            self.phase_left = 90
            self.epoch += 1

    def bodies(self):
        a, b = self.fighters
        if abs(a.x - b.x) < 850 and abs(a.y - b.y) < 1100:
            middle = max(-9075, min(9075, (a.x + b.x) // 2))
            direction = 1 if b.x >= a.x else -1
            a.x, b.x = middle - direction * 425, middle + direction * 425

    def projectile_step(self, hits):
        old = {p["id"]: p["x"] for p in self.projectiles}
        for p in self.projectiles:
            p["x"] += p["vx"]
            p["life"] -= 1
        removed = set()
        for a in self.projectiles:
            for b in self.projectiles:
                if a["id"] >= b["id"] or a["owner"] == b["owner"] or a["id"] in removed or b["id"] in removed:
                    continue
                if abs(a["y"] - b["y"]) < 600 and (old[a["id"]] - old[b["id"]]) * (a["x"] - b["x"]) <= 0:
                    if a["kind"] == b["kind"] == "beam":
                        self.begin_clash()
                        return True
                    removed.update((a["id"], b["id"]))
                    self.event("power_collision", x=(a["x"] + b["x"]) / 2000, y=a["y"] / 1000)
        for p in self.projectiles:
            if p["id"] in removed:
                continue
            target = self.fighters[1 - p["owner"]]
            if (
                min(old[p["id"]], p["x"]) - 400 <= target.x <= max(old[p["id"]], p["x"]) + 400
                and abs(p["y"] - (target.y + 1000)) < 850
            ):
                hits.append((p["owner"], p["kind"], MOVES[p["kind"]].copy(), 0))
                removed.add(p["id"])
        self.projectiles = [
            p for p in self.projectiles if p["id"] not in removed and p["life"] > 0 and abs(p["x"]) < 11000
        ]
        return False

    def hit(self, i, name, spec, contact):
        source, target = self.fighters[i], self.fighters[1 - i]
        if target.invulnerable or target.health <= 0:
            return False
        level = spec["level"]
        counter = (
            target.move == "signature"
            and target.character == "nyx"
            and 6 <= target.age < 24
            and level == "mid"
        )
        if counter:
            target.connected = True
            target.move = None
            self.event("counter", player_id=target.id)
            return self.hit(1 - i, "counter", dict(SIGNATURES["nyx"], counter=False), 0)
        guard = not target.stun and not target.y and target.held.startswith("guard") and level != "throw"
        guard = guard and not (
            level == "low"
            and target.held == "guard_high"
            or level == "overhead"
            and target.held == "guard_low"
        )
        target.guard_quiet = self.tick
        if guard and self.tick - target.guard_started < 6 and name not in ("beam", "ultimate"):
            target.guard_started = -100
            target.stats["parries"] += 1
            self.gain(target, 800)
            if name not in ("bolt", "beam"):
                source.stun = 18
                source.move = None
                source.route = []
            self.event(
                "parry",
                player_id=target.id,
                target=source.id,
                move=name,
                x=target.x / 1000,
                y=target.y / 1000 + 1,
            )
            self.hitstop = 5
            return False
        source.connected = True
        if guard:
            target.guard = max(0, target.guard - spec["guard"] * 100)
            target.stats["blocks"] += 1
            damage = min(target.health - 1, spec["damage"] // 10) if level in ("power", "ultimate") else 0
            if target.guard == 0:
                target.stun = 45
                target.held = "neutral"
                target.action = "guard_break"
                source.stats["guard_breaks"] += 1
            if source.route:
                source.route = []
                source.route_name = None
                source.held = "guard_high"
                source.hold_until = self.tick + 36
            self.event(
                "block",
                player_id=target.id,
                target=source.id,
                damage=damage,
                move=name,
                x=target.x / 1000,
                y=target.y / 1000 + 1,
            )
        else:
            if target.combo_from != i:
                target.combo_hits = target.air_hits = 0
                target.combo_break_used = False
            scale = [100, 85, 70, 55][target.combo_hits] if target.combo_hits < 4 else 40
            damage = spec["damage"] * scale // 100
            target.combo_from = i
            target.combo_hits += 1
            if target.y:
                target.air_hits += 1
            armored = (
                target.move == "signature"
                and target.character == "terra"
                and not target.armor_used
                and level not in ("throw", "ultimate")
            )
            if armored:
                target.armor_used = True
            else:
                target.stun = 24 if name not in ("heavy", "launcher", "ultimate") else 32
                target.move = None
                target.route = []
                target.route_name = None
                target.held = "neutral"
                target.action = "thrown" if name == "throw" else "hurt"
            if name == "launcher" or name == "signature" and source.character == "terra":
                target.vy = 220
                target.stun = 40
            if target.combo_hits >= 6 or target.air_hits >= 3 or name in ("throw", "ultimate"):
                target.knockdown = 45
                target.invulnerable = 45
                target.stun = 0
                target.action = "knockdown"
            target.x = max(-9500, min(9500, target.x + source.facing * (100 if name == "light" else 250)))
            if contact == 0:
                self.gain(target, 200)
                if spec["energy"] == 0:
                    self.gain(source, 500 if name == "heavy" else 300)
            source.stats["hits"] += 1
            self.event(
                "hit",
                player_id=source.id,
                target=target.id,
                damage=damage,
                move=name,
                combo=target.combo_hits,
                x=target.x / 1000,
                y=target.y / 1000 + 1,
                request_id=source.request_id,
            )
        target.health = max(0, target.health - max(0, damage))
        target.hurt_until = self.tick + 12
        source.stats["damage"] += max(0, damage)
        target.stats["received"] += max(0, damage)
        self.hitstop = max(self.hitstop, 3 if guard else 5)
        return not guard

    def begin_clash(self):
        self.phase = "clash"
        self.epoch += 1
        self.projectiles = []
        self.hitstop = 0
        self.clash = dict(pulse=1, left=48, score=[0, 0], choices={}, previous=[None, None], history=[])
        for f in self.fighters:
            f.move = None
            f.route = []
            f.route_name = None
            f.held = "neutral"
            f.action = "beam"
            f.stats["clashes"] += 1
        self.event("clash_start")

    def step_clash(self):
        c = self.clash
        c["left"] -= 1
        if c["left"] > 0:
            return
        actions = [
            c["choices"].get(f.id, dict(action="hold", source="fallback", request_id=None))
            for f in self.fighters
        ]
        yielding = [a["action"] == "yield" for a in actions]
        for i, a in enumerate(actions):
            cost = {"push": 10, "surge": 20}.get(a["action"], 0)
            if not self.spend(self.fighters[i], cost):
                a.update(action="hold", source="fallback")
            strength = {"hold": 1, "push": 2, "surge": 4, "yield": 0}[a["action"]]
            if a["action"] == c["previous"][i] == "surge":
                strength = 2
            c["score"][i] += strength
            c["previous"][i] = a["action"]
        record = dict(pulse=c["pulse"], choices=copy.deepcopy(actions), score=c["score"][:])
        c["history"].append(record)
        self.event("clash_pulse", **record)
        if any(yielding) or c["pulse"] == 3:
            winner = None if c["score"][0] == c["score"][1] else 0 if c["score"][0] > c["score"][1] else 1
            if any(yielding):
                winner = None if all(yielding) else 1 if yielding[0] else 0
            damage = 0
            if winner is not None:
                damage = 40 if any(yielding) else min(200, 140 + 8 * abs(c["score"][0] - c["score"][1]))
                source, target = self.fighters[winner], self.fighters[1 - winner]
                target.health = max(0, target.health - damage)
                target.knockdown = 45
                target.invulnerable = 45
                target.action = "knockdown"
                source.stats["damage"] += damage
                target.stats["received"] += damage
            self.event("clash_end", winner=None if winner is None else f"p{winner + 1}", damage=damage)
            self.phase = "active"
            self.epoch += 1
            for f in self.fighters:
                if not f.knockdown:
                    f.action = "neutral"
            if min(f.health for f in self.fighters) <= 0:
                if self.config.get("mode") == "training":
                    self.phase, self.phase_left = "round_over", 90
                else:
                    self.end_round()
        else:
            c["pulse"] += 1
            c["left"] = 48
            c["choices"] = {}
            self.epoch += 1

    def end_round(self):
        a, b = self.fighters
        winner = None if a.health == b.health else 0 if a.health > b.health else 1
        reason = "KO" if min(a.health, b.health) <= 0 else "timeout"
        if winner is not None:
            self.wins[winner] += 1
        record = dict(
            round=self.round,
            winner=None if winner is None else f"p{winner + 1}",
            reason=reason,
            health=[a.health, b.health],
        )
        self.history.append(record)
        self.event("round_end", **{k: v for k, v in record.items() if k != "round"})
        self.neutral()
        self.projectiles = []
        self.epoch += 1
        best = self.config.get("best_of", 3)
        if max(self.wins) >= best // 2 + 1 or self.round >= best + 2:
            self.winner = (
                None if self.wins[0] == self.wins[1] else "p1" if self.wins[0] > self.wins[1] else "p2"
            )
            if self.winner and reason == "KO" and record["winner"] == self.winner:
                self.phase = "finish"
                self.phase_left = 180
            else:
                self.finish()
        else:
            self.phase = "round_over"
            self.phase_left = 120

    def finish(self):
        self.done = True
        self.phase = "finished"
        self.epoch += 1
        self.event("match_end", winner=self.winner)

    def snapshot(self):
        fighters = []
        for f in self.fighters:
            data = asdict(f)
            data.update(
                x=f.x / 1000,
                y=f.y / 1000,
                z=0,
                energy=f.energy / 100,
                guard=f.guard / 100,
                name=FIGHTERS[f.character]["name"],
                hurt=self.tick < f.hurt_until,
            )
            if f.move:
                spec = self.definition(f)
                data["move_timing"] = dict(
                    startup=spec["startup"], active=spec["active"], recovery=spec["recovery"], frame=f.age
                )
            fighters.append(data)
        clash = (
            None
            if not self.clash
            else {k: copy.deepcopy(v) for k, v in self.clash.items() if k not in ("choices", "previous")}
        )
        return dict(
            tick=self.tick,
            epoch=self.epoch,
            round=self.round,
            phase=self.phase,
            phase_left=self.phase_left,
            timer=self.timer / 60,
            best_of=self.config.get("best_of", 3),
            wins=self.wins[:],
            rounds=copy.deepcopy(self.history),
            winner=self.winner,
            done=self.done,
            fighters=fighters,
            projectiles=[
                dict(p, x=p["x"] / 1000, y=p["y"] / 1000, origin=p["origin"] / 1000) for p in self.projectiles
            ],
            clash=clash,
            cinematic=self.cinematic,
            events=copy.deepcopy(self.events[-24:]),
            arena=self.config.get("arena_id", "sanctuary"),
            rules_version=RULES_VERSION,
            content_version=CONTENT_VERSION,
        )
