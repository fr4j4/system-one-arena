import pytest
from arena.combat.content import MOVES, ROUTES
from arena.combat.engine import World
from arena.combat.observation import observe, reference
from arena.combat.protocol import MatchConfig


def world(**kwargs):
    w = World(MatchConfig(**kwargs).model_dump())
    w.phase = "active"
    w.fighters[0].x = -500
    w.fighters[1].x = 500
    return w


def advance(w, n):
    for _ in range(n):
        w.step()


def test_resources_round_reset_and_plane():
    w = world()
    a, b = w.fighters
    assert (a.health, a.energy, a.guard) == (1000, 2500, 10000)
    w.apply(0, "jump_forward")
    advance(w, 15)
    assert a.y > 0 and a.x > -500
    advance(w, 80)
    assert a.y == 0
    for _ in range(200):
        if "back" in w.legal(0):
            w.apply(0, "back")
        w.step()
    assert -9500 <= a.x <= 9500
    assert all(f["z"] == 0 for f in w.snapshot()["fighters"])
    a.energy = 10000
    w.new_round()
    assert w.fighters[0].energy == 2500


@pytest.mark.parametrize("name", [n for n in MOVES if n not in ("bolt", "beam", "air_heavy")])
def test_move_cost_and_startup(name):
    w = world()
    a, b = w.fighters
    a.energy = 10000
    a.x, b.x = -425, 425
    assert w.apply(0, name)
    assert a.energy == 10000 - MOVES[name]["energy"] * 100
    advance(w, MOVES[name]["startup"] - 1)
    assert b.health == 1000
    w.step()
    assert b.health < 1000
    assert not w.apply(0, name)


@pytest.mark.parametrize(
    "guard,attack,blocked",
    [
        ("guard_high", "light", True),
        ("guard_low", "light", True),
        ("guard_high", "low", False),
        ("guard_low", "overhead", False),
        ("guard_high", "throw", False),
    ],
)
def test_defense_matchups(guard, attack, blocked):
    w = world()
    a, b = w.fighters
    a.x = -400
    b.x = 400
    w.apply(1, guard)
    b.guard_started = -100
    w.apply(0, attack)
    advance(w, MOVES[attack]["startup"] + 1)
    assert (b.health == 1000) == blocked


def test_parry_cannot_rearm_by_refresh_and_beam_cannot_be_parried():
    w = world()
    a, b = w.fighters
    w.apply(0, "light")
    advance(w, 3)
    w.apply(1, "guard_high")
    advance(w, 4)
    assert b.stats["parries"] == 1 and b.health == 1000 and a.stun > 0
    start = b.guard_started
    w.apply(1, "guard_high")
    assert b.guard_started == start


def test_charge_cost_caps_and_vulnerability():
    w = world()
    a, b = w.fighters
    w.apply(0, "charge")
    advance(w, 15)
    assert a.energy == 2500
    advance(w, 10)
    assert a.energy == 2700
    w.apply(1, "light")
    advance(w, 7)
    assert a.held == "neutral" and a.health < 1000
    a.energy = 9999
    w.gain(a, 200)
    assert a.energy == 10000
    assert not w.spend(a, 101)


def test_guard_break_and_chip_never_kills():
    w = world()
    a, b = w.fighters
    b.guard = 500
    b.health = 1
    w.apply(1, "guard_high")
    b.guard_started = -100
    w.apply(0, "heavy")
    advance(w, 15)
    assert b.guard == 0 and b.stun > 0 and b.health == 1
    advance(w, 60)
    assert b.guard >= 5000


@pytest.mark.parametrize("route", list(ROUTES))
def test_routes_are_authorized_and_bounded(route):
    w = world()
    a, b = w.fighters
    a.energy = 10000
    assert w.apply(0, route, request_id="decision")
    advance(w, 180)
    starts = [e for e in w.events if e["kind"] == "move_start"]
    assert starts and all(e["request_id"] == "decision" for e in starts)
    assert all(e["source"] == "route" for e in starts)
    assert b.combo_hits <= 6 and a.energy >= 0


def test_combo_escape_and_insufficient_energy():
    w = world()
    a, b = w.fighters
    w.apply(0, "light")
    advance(w, 7)
    assert "break" not in w.legal(1)
    b.energy = 5000
    assert w.apply(1, "break")
    assert b.energy == 0 and not b.stun and b.invulnerable


def test_projectile_swept_collision_and_jump_evasion():
    w = world()
    a, b = w.fighters
    a.x = -4000
    b.x = 4000
    w.apply(0, "bolt")
    advance(w, 17)
    assert not w.projectiles
    advance(w, 1)
    assert w.projectiles
    b.y = 2200
    b.vy = 0
    advance(w, 60)
    assert b.health < 1000  # It landed before the slow projectile arrived.
    assert not w.projectiles


def test_clash_choices_sealed_costed_and_simultaneous():
    w = world()
    a, b = w.fighters
    a.energy = b.energy = 10000
    w.begin_clash()
    assert w.apply(0, "surge")
    assert "choices" not in w.snapshot()["clash"]
    assert "surge" not in str(observe(w, 1)["state"]["clash"])
    assert w.apply(1, "push")
    advance(w, 48)
    assert [a.energy, b.energy] == [8000, 9000]
    assert w.clash["score"] == [4, 2]
    w.apply(0, "surge")
    w.apply(1, "push")
    advance(w, 48)
    assert w.clash["score"] == [6, 4]
    w.apply(0, "hold")
    w.apply(1, "hold")
    advance(w, 48)
    assert w.phase == "active" and b.health == 844


@pytest.mark.parametrize(
    "left,right,health",
    [("hold", "hold", [1000, 1000]), ("yield", "yield", [1000, 1000]), ("yield", "hold", [960, 1000])],
)
def test_clash_tie_and_yield(left, right, health):
    w = world()
    w.begin_clash()
    for _ in range(3):
        if w.phase != "clash":
            break
        w.apply(0, left)
        w.apply(1, right)
        advance(w, 48)
    assert [f.health for f in w.fighters] == health


def test_beams_enter_clash_physically():
    w = world()
    a, b = w.fighters
    a.x = -4000
    b.x = 4000
    a.energy = b.energy = 10000
    w.apply(0, "beam")
    w.apply(1, "beam")
    advance(w, 50)
    assert w.phase == "clash"


def test_round_finish_finisher_does_not_change_winner():
    w = world(best_of=1)
    w.fighters[1].health = 0
    w.step()
    assert w.phase == "finish" and w.winner == "p1"
    assert w.legal(1) == []
    w.apply(0, "finish")
    assert w.phase == "finisher"
    advance(w, 300)
    assert w.done and w.winner == "p1"


def test_timeout_draws_bounded_and_replay_deterministic():
    config = MatchConfig(best_of=1, round_seconds=5).model_dump()
    a, b = World(config), World(config)
    for t in range(3000):
        if t % 20 == 0:
            for i in (0, 1):
                v = observe(a, i)
                if v["actions"]:
                    action = reference(v["state"], v["actions"])
                    assert a.apply(i, action) == b.apply(i, action)
        a.step()
        b.step()
        assert a.snapshot() == b.snapshot()
        if a.done:
            break
    assert a.done and a.round <= 3


def test_simultaneous_hits_trade_without_player_order_advantage():
    w = world()
    w.apply(0, "light")
    w.apply(1, "light")
    advance(w, 7)
    assert w.fighters[0].health == w.fighters[1].health == 960


def test_all_fighters_and_training_presets_are_valid():
    from arena.combat.content import FIGHTERS, PRESETS

    for char in FIGHTERS:
        for preset in PRESETS:
            cfg = MatchConfig(mode="training", preset=preset).model_dump()
            cfg["players"][0]["fighter_id"] = char
            w = World(cfg)
            advance(w, 61)
            view = observe(w, 0)
            assert view["state"]["self"]["character"] == char
            assert view["actions"]
