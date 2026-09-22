from typing import Literal

from pydantic import Field, model_validator

from arena.protocol import StrictModel

from .content import ARENAS, FIGHTERS, PRESETS


class Slot(StrictModel):
    controller: Literal["model", "human", "baseline"] = "baseline"
    fighter_id: str = "ember"
    model_profile_id: str = "reference"

    @model_validator(mode="after")
    def fighter(self):
        if self.fighter_id not in FIGHTERS:
            raise ValueError("Personaje desconocido")
        return self


class MatchConfig(StrictModel):
    players: list[Slot] = Field(
        default_factory=lambda: [Slot(), Slot(fighter_id="flux")], min_length=2, max_length=2
    )
    arena_id: str = "sanctuary"
    mode: Literal["duel", "training"] = "duel"
    preset: str = "neutral"
    best_of: Literal[1, 3, 5] = 3
    round_seconds: int = Field(default=90, ge=5, le=120)
    decision_hz: float = Field(default=3, ge=1, le=10)
    budget_ms: int = Field(default=800, ge=100, le=5000)
    max_age_ms: int = Field(default=1000, ge=100, le=6000)
    pace: Literal["native", "equal_windows"] = "native"
    seed: int = Field(default=42, ge=0, le=2147483647)
    max_seconds: int = Field(default=900, ge=1, le=3600)

    @model_validator(mode="after")
    def valid(self):
        if self.arena_id not in ARENAS or self.preset not in PRESETS:
            raise ValueError("Arena o situación desconocida")
        if sum(p.controller == "human" for p in self.players) > 1:
            raise ValueError("Esta versión admite una persona local por partida")
        return self


class Control(StrictModel):
    command: Literal["pause", "resume", "stop", "reset", "skip", "step"]


class SeriesConfig(StrictModel):
    match: MatchConfig = Field(default_factory=MatchConfig)
    pairs: int = Field(default=2, ge=1, le=50)

    @model_validator(mode="after")
    def no_human(self):
        if any(p.controller == "human" for p in self.match.players):
            raise ValueError("Las series requieren dos controladores automáticos")
        self.match.mode = "duel"
        return self
