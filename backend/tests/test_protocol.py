import pytest
from arena.protocol import DecisionRequest, Question, normalize
from pydantic import ValidationError


@pytest.fixture
def req():
    return DecisionRequest(
        run_id="r",
        episode_id="e",
        state_seq=0,
        schema_id="s",
        state={"text": "hello"},
        questions={"route": Question(type="choice", instructions="route", criteria={"a": "A", "b": "B"})},
    )


def test_confidence_is_preserved_not_inferred(req):
    result = normalize(
        {"answers": {"route": {"choice": "a", "confidence": 0.2, "probabilities": {"a": 0.9, "b": 0.1}}}},
        req,
        "provider",
    )
    assert result.answers["route"].confidence == 0.2
    assert result.answers["route"].probabilities["a"] == 0.9


def test_missing_distribution_stays_missing(req):
    answer = normalize({"answers": {"route": {"choice": "a"}}}, req, "generic").answers["route"]
    assert answer.confidence is None and answer.probabilities is None


@pytest.mark.parametrize(
    "item",
    [
        {"choice": "c"},
        {"choice": "a", "probabilities": {"a": 1}},
        {"choice": "a", "probabilities": {"a": 0.8, "b": 0.8}},
        {"choice": "a", "probabilities": {"a": float("nan"), "b": 0}},
        {"type": "noul", "choice": "a"},
        {"choice": "a", "confidence": 1.1},
    ],
)
def test_malformed_results_rejected(req, item):
    with pytest.raises(ValueError):
        normalize({"answers": {"route": item}}, req, "bad")


def test_missing_answer(req):
    with pytest.raises(ValueError):
        normalize({"answers": {}}, req, "bad")


@pytest.mark.parametrize("value", [-0.1, 1.1, True, "0.5", float("inf")])
def test_boolean_probability_bounds(req, value):
    req.questions = {"p": Question(type="boolean_probability", instructions="true?")}
    with pytest.raises(ValueError):
        normalize({"answers": {"p": {"noul": value}}}, req, "bad")


def test_neutral_to_provider_mapping():
    assert (
        Question(type="ordinal", instructions="Urgency", criteria=["low", "high"]).provider_dict()["type"]
        == "score"
    )
    assert Question(type="boolean_probability", instructions="True?").provider_dict()["type"] == "noul"


@pytest.mark.parametrize(
    "data",
    [
        {"type": "choice", "instructions": "x", "criteria": []},
        {"type": "choice", "instructions": "x", "criteria": {}},
        {"type": "ordinal", "instructions": "x", "criteria": ["one"]},
        {"type": "boolean_probability", "instructions": "x", "criteria": {"x": "y"}},
    ],
)
def test_question_schema(data):
    with pytest.raises(ValidationError):
        Question(**data)
