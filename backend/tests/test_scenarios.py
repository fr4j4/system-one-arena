import copy

import pytest
from arena.adapters import ReferenceAdapter
from arena.protocol import DecisionRequest
from arena.scenarios.business import BUSINESS, Business, default_graph, validate_graph
from arena.scenarios.games import CATALOG, Game, minimax_move, reference_action


@pytest.mark.parametrize("name", [x[0] for x in CATALOG])
def test_game_seed_and_actions_are_deterministic(name):
    a, b = Game(name, 19), Game(name, 19)
    for _ in range(50):
        assert a.observe() == b.observe()
        if a.done:
            break
        action = reference_action(a.observe(), a.legal_actions())
        assert a.apply(action) and b.apply(action)
        for _ in range(12):
            a.tick(1 / 60)
            b.tick(1 / 60)
    assert a.observe() == b.observe()


@pytest.mark.parametrize("name", [x[0] for x in CATALOG])
def test_illegal_action_does_not_mutate(name):
    g = Game(name)
    before = g.observe()
    assert not g.apply("__invalid__")
    assert g.observe() == before


def test_tictactoe_optimal_players_draw():
    game = Game("tic-tac-toe")
    while not game.done:
        game.apply(str(minimax_move(game.s["board"], 1)))
    assert game.outcome == "draw"


def test_snake_wall_collision_and_tail_movement():
    g = Game("snake")
    g.s["body"] = [[15, 0], [14, 0], [13, 0]]
    g.tick(0.2)
    assert g.done and g.outcome == "collision"


def test_tetris_lines_clear():
    g = Game("tetris")
    g.s["board"][19] = [1] * 10
    g.s["board"][19][:4] = [0] * 4
    g.s.update(cells=[[0, 0], [1, 0], [2, 0], [3, 0]], x=0, y=0)
    assert g.apply("drop")
    assert g.s["lines"] == 1 and g.score == 100


@pytest.mark.parametrize("name", [x[0] for x in BUSINESS])
async def test_all_business_scenarios_finish_without_exposing_labels(name):
    b = Business(name)
    for _ in range(len(b.items) * 4):
        if b.done:
            break
        state = b.observe()
        assert "expected" not in state
        req = DecisionRequest(
            run_id="test",
            episode_id="e",
            state_seq=b.seq,
            schema_id=name,
            state=state,
            questions=b.questions(),
        )
        result = await ReferenceAdapter().decide(req)
        b.apply(result.model_dump())
    assert b.done and len(b.results) == len(b.items)


@pytest.mark.parametrize("template", ["support", "email", "incident"])
def test_graph_templates_are_valid(template):
    validate_graph(default_graph(template))


def test_graph_rejects_cycles_missing_paths_and_forward_references():
    graph = default_graph()
    graph["nodes"][0]["next"] = graph["start"]
    with pytest.raises(ValueError, match="ciclo"):
        validate_graph(graph)
    graph = default_graph()
    graph["nodes"][0]["next"] = "absent"
    with pytest.raises(ValueError, match="inexistente"):
        validate_graph(graph)
    graph = default_graph()
    graph["nodes"][2]["source"] = "future"
    with pytest.raises(ValueError, match="anterior"):
        validate_graph(graph)


def test_observation_is_a_copy():
    g = Game("snake")
    obs = copy.deepcopy(g.observe())
    g.apply("right")
    g.tick(0.2)
    assert obs["body"] != g.s["body"]
