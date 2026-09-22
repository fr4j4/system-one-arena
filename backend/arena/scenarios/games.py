"""Small deterministic worlds. Observations expose no hidden opponent intentions."""

from __future__ import annotations

import copy
import random
from collections import deque

from arena.protocol import Question
from arena.scenarios.fighting import FightingWorld, fighting_reference

CATALOG = [
    ("tic-tac-toe", "Tic-tac-toe", "Estrategia", "Amenazas, reglas y decisiones por turnos"),
    ("snake", "Snake", "Navegación", "Sobrevivir, buscar comida y evitar colisiones"),
    ("pong", "Pong", "Reacción", "Anticipar trayectorias bajo latencia"),
    ("tetris", "Tetris", "Planificación", "Ordenar el tablero mientras cae la pieza"),
    ("fighting", "Fighting", "Timing", "Atacar, defender y administrar energía"),
    ("space-invaders", "Space Invaders", "Reacción", "Esquivar proyectiles y alcanzar objetivos"),
]


class Game:
    def __init__(self, name: str, seed=42, options=None):
        self.name = name
        self.rng = random.Random(seed)
        self.options = options or {}
        self.elapsed = 0.0
        self.score = 0
        self.done = False
        self.outcome = None
        self.action = "neutral"
        self.clock = 0.0
        self.decisions = 0
        self.s = {}
        self._reset()

    def _reset(self):
        if self.name == "tic-tac-toe":
            self.s = {"board": [0] * 9, "player": 1}
        elif self.name == "snake":
            self.s = {"size": 16, "body": [[7, 8], [6, 8], [5, 8]], "direction": [1, 0]}
            self._food()
        elif self.name == "pong":
            self.s = {
                "ball": [50.0, 30.0],
                "velocity": [25.0, 17.0],
                "paddle": 30.0,
                "opponent": 30.0,
                "hits": 0,
                "misses": 0,
                "width": 100,
                "height": 60,
            }
        elif self.name == "tetris":
            self.s = {"board": [[0] * 10 for _ in range(20)], "next": self.rng.randrange(7), "lines": 0}
            self._piece()
        elif self.name == "fighting":
            self.fight = FightingWorld(self.options)
        elif self.name == "space-invaders":
            self.s = {
                "x": 50.0,
                "enemies": [[15.0 + j * 14, 8.0 + i * 9] for i in range(3) for j in range(6)],
                "bullets": [],
                "enemy_bullets": [],
                "direction": 1,
                "cooldown": 0.0,
                "lives": 3,
            }
        else:
            raise ValueError("Unknown game")

    def _food(self):
        cells = [[x, y] for y in range(16) for x in range(16) if [x, y] not in self.s["body"]]
        if not cells:
            self.done, self.outcome = True, "win"
        else:
            self.s["food"] = self.rng.choice(cells)

    def legal_actions(self):
        if self.name == "fighting":
            return self.fight.legal_actions()
        if self.done:
            return []
        if self.name == "tic-tac-toe":
            return [str(i) for i, v in enumerate(self.s["board"]) if not v]
        if self.name == "snake":
            return ["straight", "left", "right"]
        if self.name == "pong":
            return ["up", "down", "neutral"]
        if self.name == "tetris":
            if self.options.get("tetris_control") == "placement":
                return [
                    f"place:{r}:{x}"
                    for r in range(4)
                    for x in range(10)
                    if self._fits(self._rotated(r), x, self.s["y"])
                ]
            return ["left", "right", "rotate", "down", "drop", "neutral"]
        return ["left", "right", "fire", "left_fire", "right_fire", "neutral"]

    def observe(self, enriched=False):
        if self.name == "fighting":
            return self.fight.observe()
        state = {
            "scenario": self.name,
            **copy.deepcopy(self.s),
            "elapsed": round(self.elapsed, 3),
            "score": self.score,
            "done": self.done,
            "outcome": self.outcome,
        }
        if enriched and self.name == "snake":
            x, y = self.s["body"][0]
            state["food_delta"] = [self.s["food"][0] - x, self.s["food"][1] - y]
            state["immediate_danger"] = {}
            dx, dy = self.s["direction"]
            for a, (vx, vy) in {"straight": (dx, dy), "left": (dy, -dx), "right": (-dy, dx)}.items():
                p = [x + vx, y + vy]
                state["immediate_danger"][a] = (
                    not (0 <= p[0] < 16 and 0 <= p[1] < 16) or p in self.s["body"][:-1]
                )
        if enriched and self.name == "pong":
            state["ball_paddle_delta"] = self.s["ball"][1] - self.s["paddle"]
        return state

    def questions(self):
        if self.name == "fighting":
            return self.fight.questions()
        rules = {
            "tic-tac-toe": "You are player 1 (X). Board is row-major, 0 empty, 1 yours, -1 opponent. Win or block a line.",
            "snake": "Coordinates: x right, y down. Turn relative to current direction. Eat food, avoid walls and body.",
            "pong": "Control the left paddle. Follow the incoming ball and avoid missing. y increases downward.",
            "tetris": "Complete horizontal lines. Avoid holes and tall stacks. Coordinates x right, y down.",
            "space-invaders": "Move along x, shoot enemies above, dodge enemy bullets approaching y=90.",
        }
        return {
            "action": Question(
                type="choice",
                instructions=rules[self.name],
                criteria={a: a.replace("_", " ") for a in self.legal_actions()},
            )
        }

    def apply(self, action):
        if self.name == "fighting":
            return self.fight.apply(action)
        if action not in self.legal_actions():
            return False
        self.decisions += 1
        self.action = action
        if self.name == "tic-tac-toe":
            board = self.s["board"]
            board[int(action)] = 1
            self._ttt_done()
            if not self.done:
                other = (
                    self.rng.choice([i for i, value in enumerate(board) if value == 0])
                    if self.options.get("opponent") == "random"
                    else minimax_move(board, -1)
                )
                board[other] = -1
                self._ttt_done()
        elif self.name == "snake":
            dx, dy = self.s["direction"]
            if action == "left":
                self.s["direction"] = [dy, -dx]
            elif action == "right":
                self.s["direction"] = [-dy, dx]
        elif self.name == "tetris":
            s = self.s
            if action.startswith("place:"):
                _, r, x = action.split(":")
                s["cells"], s["x"] = self._rotated(int(r)), int(x)
                action = "drop"
            if action in ("left", "right"):
                nx = s["x"] + (-1 if action == "left" else 1)
                if self._fits(s["cells"], nx, s["y"]):
                    s["x"] = nx
            elif action == "rotate":
                cells = self._rotated(1)
                if self._fits(cells, s["x"], s["y"]):
                    s["cells"] = cells
            if action in ("drop", "down"):
                while self._fits(s["cells"], s["x"], s["y"] + 1):
                    s["y"] += 1
                    if action == "down":
                        break
                if action == "drop":
                    self._lock()
        return True

    def tick(self, dt):
        if self.name == "fighting":
            self.fight.tick(dt)
            self.elapsed, self.score = self.fight.elapsed, self.fight.score
            self.done, self.outcome = self.fight.done, self.fight.outcome
            return
        if self.done:
            return
        self.elapsed += dt
        self.clock += dt
        s = self.s
        if self.name == "snake" and self.clock >= 0.18:
            self.clock -= 0.18
            dx, dy = s["direction"]
            p = [s["body"][0][0] + dx, s["body"][0][1] + dy]
            eating = p == s["food"]
            if not (0 <= p[0] < 16 and 0 <= p[1] < 16) or p in (s["body"] if eating else s["body"][:-1]):
                self.done, self.outcome = True, "collision"
                return
            s["body"].insert(0, p)
            if eating:
                self.score += 1
                self._food()
            else:
                s["body"].pop()
        elif self.name == "pong":
            s["paddle"] = max(6, min(54, s["paddle"] + {"up": -36, "down": 36}.get(self.action, 0) * dt))
            s["opponent"] += max(-26 * dt, min(26 * dt, s["ball"][1] - s["opponent"]))
            x, y = s["ball"]
            vx, vy = s["velocity"]
            x, y = x + vx * dt, y + vy * dt
            if y < 1 or y > 59:
                vy = -vy
                y = max(1, min(59, y))
            if x <= 5 and vx < 0 and abs(y - s["paddle"]) <= 7:
                vx = abs(vx) * 1.025
                s["hits"] += 1
                self.score += 1
            if x >= 95 and vx > 0 and abs(y - s["opponent"]) <= 7:
                vx = -abs(vx)
            if x < 0 or x > 100:
                if x < 0:
                    s["misses"] += 1
                else:
                    self.score += 5
                x, y, vx, vy = 50.0, 30.0, -25.0, self.rng.choice([-17.0, 17.0])
                if s["misses"] >= 5:
                    self.done, self.outcome = True, "five_misses"
            s["ball"], s["velocity"] = [x, y], [vx, vy]
        elif self.name == "tetris" and self.clock >= 0.55:
            self.clock -= 0.55
            if self._fits(s["cells"], s["x"], s["y"] + 1):
                s["y"] += 1
            else:
                self._lock()
        elif self.name == "space-invaders":
            direction = -1 if "left" in self.action else 1 if "right" in self.action else 0
            s["x"] = max(3, min(97, s["x"] + direction * 36 * dt))
            s["cooldown"] = max(0, s["cooldown"] - dt)
            if "fire" in self.action and s["cooldown"] == 0:
                s["bullets"].append([s["x"], 86.0])
                s["cooldown"] = 0.3
            for p in s["enemies"]:
                p[0] += s["direction"] * 8 * dt
            if any(p[0] < 3 or p[0] > 97 for p in s["enemies"]):
                s["direction"] *= -1
                for p in s["enemies"]:
                    p[0] = max(3, min(97, p[0]))
                    p[1] += 3
            if self.clock >= 0.6 and s["enemies"]:
                self.clock -= 0.6
                s["enemy_bullets"].append(list(self.rng.choice(s["enemies"])))
            for p in s["bullets"]:
                p[1] -= 65 * dt
            for p in s["enemy_bullets"]:
                p[1] += 35 * dt
            for bullet in s["bullets"][:]:
                hit = next(
                    (p for p in s["enemies"] if abs(p[0] - bullet[0]) < 4 and abs(p[1] - bullet[1]) < 3), None
                )
                if hit:
                    s["enemies"].remove(hit)
                    s["bullets"].remove(bullet)
                    self.score += 10
            for p in s["enemy_bullets"][:]:
                if abs(p[0] - s["x"]) < 4 and 86 < p[1] < 94:
                    s["lives"] -= 1
                    s["enemy_bullets"].remove(p)
            s["bullets"] = [p for p in s["bullets"] if p[1] >= 0]
            s["enemy_bullets"] = [p for p in s["enemy_bullets"] if p[1] <= 100]
            if not s["enemies"] or s["lives"] <= 0 or any(p[1] > 82 for p in s["enemies"]):
                self.done, self.outcome = True, "win" if not s["enemies"] else "loss"

    def neutral(self):
        if self.name == "fighting":
            self.fight.neutral()
            return
        self.action = "neutral"

    def _ttt_done(self):
        w = winner(self.s["board"])
        if w or 0 not in self.s["board"]:
            self.done = True
            self.outcome = "win" if w == 1 else "loss" if w == -1 else "draw"
            self.score = w

    def _piece(self):
        shapes = [
            [[0, 0], [1, 0], [2, 0], [3, 0]],
            [[0, 0], [1, 0], [0, 1], [1, 1]],
            [[1, 0], [0, 1], [1, 1], [2, 1]],
            [[1, 0], [2, 0], [0, 1], [1, 1]],
            [[0, 0], [1, 0], [1, 1], [2, 1]],
            [[0, 0], [0, 1], [1, 1], [2, 1]],
            [[2, 0], [0, 1], [1, 1], [2, 1]],
        ]
        self.s.update(cells=copy.deepcopy(shapes[self.s["next"]]), x=3, y=0, next=self.rng.randrange(7))
        if not self._fits(self.s["cells"], 3, 0):
            self.done, self.outcome = True, "stack_overflow"

    def _rotated(self, n):
        cells = copy.deepcopy(self.s["cells"])
        for _ in range(n):
            cells = [[-y, x] for x, y in cells]
            mx, my = min(x for x, y in cells), min(y for x, y in cells)
            cells = [[x - mx, y - my] for x, y in cells]
        return cells

    def _fits(self, cells, x, y):
        return all(
            0 <= x + cx < 10 and 0 <= y + cy < 20 and not self.s["board"][y + cy][x + cx] for cx, cy in cells
        )

    def _lock(self):
        s = self.s
        for cx, cy in s["cells"]:
            s["board"][s["y"] + cy][s["x"] + cx] = 1
        rows = [r for r in s["board"] if not all(r)]
        n = 20 - len(rows)
        s["board"] = [[0] * 10 for _ in range(n)] + rows
        s["lines"] += n
        self.score += [0, 100, 300, 500, 800][n]
        self._piece()


def winner(b):
    for a, c, d in [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]:
        if b[a] and b[a] == b[c] == b[d]:
            return b[a]
    return 0


def minimax_move(board, player):
    from functools import lru_cache

    @lru_cache(None)
    def search(b, p):
        w = winner(b)
        if w or 0 not in b:
            return w * p
        scores = []
        for i, v in enumerate(b):
            if not v:
                new = list(b)
                new[i] = p
                scores.append(-search(tuple(new), -p))
        return max(scores)

    candidates = []
    for i, v in enumerate(board):
        if not v:
            b = list(board)
            b[i] = player
            candidates.append((-search(tuple(b), -player), i))
    return max(candidates)[1]


def reference_action(state, actions):
    name = state.get("scenario")
    if name == "tic-tac-toe":
        return str(minimax_move(state["board"], 1))
    if name == "snake":
        x, y = state["body"][0]
        dx, dy = state["direction"]
        blocked = {tuple(p) for p in state["body"][:-1]}
        food = tuple(state["food"])
        candidates = []
        for a, (vx, vy) in {"straight": (dx, dy), "left": (dy, -dx), "right": (-dy, dx)}.items():
            pos = (x + vx, y + vy)
            if pos in blocked or not (0 <= pos[0] < 16 and 0 <= pos[1] < 16):
                continue
            queue, seen, distance = deque([(pos, 0)]), {pos}, 999
            while queue:
                p, n = queue.popleft()
                if p == food:
                    distance = min(distance, n)
                for xx, yy in [(p[0] + 1, p[1]), (p[0] - 1, p[1]), (p[0], p[1] + 1), (p[0], p[1] - 1)]:
                    q = (xx, yy)
                    if 0 <= xx < 16 and 0 <= yy < 16 and q not in blocked and q not in seen:
                        seen.add(q)
                        queue.append((q, n + 1))
            candidates.append((distance, -len(seen), a))
        return min(candidates)[2] if candidates else "straight"
    if name == "pong":
        d = state["ball"][1] - state["paddle"]
        return "up" if d < -2 else "down" if d > 2 else "neutral"
    if name == "fighting":
        return fighting_reference(state, actions)
    if name == "space-invaders":
        if any(abs(p[0] - state["x"]) < 8 and p[1] > 62 for p in state["enemy_bullets"]):
            return "left_fire" if state["x"] > 50 else "right_fire"
        target = min(state["enemies"], key=lambda p: abs(p[0] - state["x"]), default=[state["x"], 0])[0]
        return (
            "fire" if abs(target - state["x"]) < 3 else "left_fire" if target < state["x"] else "right_fire"
        )
    if name == "tetris":
        # Exhaustively evaluate reachable hard-drop placements using aggregate height, holes and lines.
        g = Game("tetris", 0)
        g.s = copy.deepcopy(state)
        best = None
        for r in range(4):
            cells = g._rotated(r)
            for x in range(10):
                y = state["y"]
                if not g._fits(cells, x, y):
                    continue
                while g._fits(cells, x, y + 1):
                    y += 1
                b = copy.deepcopy(state["board"])
                for cx, cy in cells:
                    b[y + cy][x + cx] = 1
                lines = sum(all(row) for row in b)
                heights, holes = [], 0
                for col in range(10):
                    h = next((20 - i for i in range(20) if b[i][col]), 0)
                    heights.append(h)
                    holes += sum(not b[i][col] for i in range(20 - h, 20))
                cost = (
                    sum(heights)
                    + holes * 8
                    + sum(abs(a - b) for a, b in zip(heights, heights[1:]))
                    - lines * 12
                )
                candidate = (cost, r, x)
                if best is None or candidate < best:
                    best = candidate
        if best:
            _, r, x = best
            if actions[0].startswith("place:"):
                return f"place:{r}:{x}"
            if r:
                return "rotate"
            return "left" if state["x"] > x else "right" if state["x"] < x else "drop"
    return actions[0]
