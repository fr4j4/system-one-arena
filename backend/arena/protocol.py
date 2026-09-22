"""Provider-neutral, versioned wire contract. No provider SDK types escape this module."""

from __future__ import annotations

import math
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Question(StrictModel):
    type: Literal["choice", "ordinal", "boolean_probability"]
    instructions: str = Field(min_length=1, max_length=8000)
    criteria: dict[str, str] | list[str] | None = None

    @model_validator(mode="after")
    def validate_criteria(self):
        if self.type == "choice" and (
            not isinstance(self.criteria, dict) or not 1 <= len(self.criteria) <= 255
        ):
            raise ValueError("choice requires 1–255 named options")
        if self.type == "ordinal" and (
            not isinstance(self.criteria, list) or not 2 <= len(self.criteria) <= 10
        ):
            raise ValueError("ordinal requires 2–10 ordered descriptions")
        if self.type == "boolean_probability" and self.criteria is not None:
            raise ValueError("boolean_probability has no criteria")
        return self

    def provider_dict(self) -> dict:
        result = self.model_dump(exclude_none=True)
        result["type"] = {"ordinal": "score", "boolean_probability": "noul"}.get(self.type, self.type)
        return result


class DecisionRequest(StrictModel):
    protocol_version: Literal["1.0"] = "1.0"
    run_id: str
    request_id: str = Field(default_factory=lambda: uuid4().hex)
    episode_id: str
    state_seq: int = Field(ge=0)
    schema_id: str
    state: dict[str, Any]
    questions: dict[str, Question]
    allowed_actions: list[str] = []
    budget_ms: int = Field(default=1000, ge=10, le=60000)
    max_state_age_ms: int = Field(default=1500, ge=10, le=60000)


class Answer(StrictModel):
    type: Literal["choice", "ordinal", "boolean_probability"]
    value: str | float
    probabilities: dict[str, float] | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class DecisionResult(StrictModel):
    request_id: str
    model: str
    answers: dict[str, Answer]
    timings: dict[str, float | None] = {}
    usage: dict[str, Any] = {}
    raw: dict[str, Any] = {}


def normalize(raw: dict, request: DecisionRequest, model: str) -> DecisionResult:
    answers = {}
    for key, question in request.questions.items():
        item = raw.get("answers", {}).get(key)
        if not isinstance(item, dict):
            raise ValueError(f"Missing answer: {key}")
        expected = {"choice": "choice", "ordinal": "score", "boolean_probability": "noul"}[question.type]
        if "type" in item and item["type"] != expected:
            raise ValueError(f"Wrong answer type: {key}")
        value = item.get(expected)
        if question.type == "choice":
            if not isinstance(value, str) or value not in question.criteria:
                raise ValueError(f"Unknown choice: {key}")
            labels = set(question.criteria)
        else:
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
                raise ValueError(f"Invalid numeric answer: {key}")
            maximum = len(question.criteria) - 1 if question.type == "ordinal" else 1
            if not 0 <= value <= maximum:
                raise ValueError(f"Out of range: {key}")
            labels = set(map(str, range(len(question.criteria)))) if question.type == "ordinal" else set()
        probabilities = item.get("probabilities")
        if probabilities is not None:
            if not isinstance(probabilities, dict) or set(probabilities) != labels:
                raise ValueError(f"Incomplete distribution: {key}")
            if (
                any(
                    isinstance(p, bool)
                    or not isinstance(p, (int, float))
                    or not math.isfinite(p)
                    or not 0 <= p <= 1
                    for p in probabilities.values()
                )
                or abs(sum(probabilities.values()) - 1) > 0.02
            ):
                raise ValueError(f"Invalid distribution: {key}")
        answers[key] = Answer(
            type=question.type, value=value, probabilities=probabilities, confidence=item.get("confidence")
        )
    return DecisionResult(
        request_id=request.request_id,
        model=raw.get("model", model),
        answers=answers,
        usage=raw.get("usage", {}),
        raw=raw,
    )


class RunConfig(StrictModel):
    scenario: str = "snake"
    provider: str = "simulated"
    mode: Literal["realtime", "step"] = "realtime"
    seed: int = Field(default=42, ge=0, le=2147483647)
    decision_hz: float = Field(default=10, ge=1, le=30)
    budget_ms: int = Field(default=1000, ge=10, le=60000)
    max_state_age_ms: int = Field(default=1500, ge=10, le=60000)
    speed: float = Field(default=1, ge=0.1, le=3)
    representation: Literal["direct", "enriched"] = "direct"
    controller: Literal["model", "human"] = "model"
    options: dict[str, Any] = {}
    dataset: list[dict[str, Any]] | None = Field(default=None, max_length=10000)
    graph: dict[str, Any] | None = None
    max_seconds: int = Field(default=180, ge=1, le=3600)
