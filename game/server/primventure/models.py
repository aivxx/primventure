from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


QuestKind = Literal["orientation", "room", "neighborhood_boss", "city_boss", "floor_boss"]
LessonBeatKind = Literal["concept", "api", "pitfall", "recap"]


class Question(BaseModel):
    prompt: str
    choices: list[str] = Field(default_factory=list)
    answer: int | None = None
    answer_key: str = ""
    explanation: str = ""


class LessonBeat(BaseModel):
    kind: LessonBeatKind
    heading: str
    # The System narrates; `body` and `points` stay in neutral instructional
    # voice so the host's commentary never has to carry the technical load.
    system: str = ""
    body: str = ""
    points: list[str] = Field(default_factory=list)
    code: str = ""


class LessonCard(BaseModel):
    source: str
    title: str
    objective: str
    intro: str
    beats: list[LessonBeat] = Field(min_length=1)
    apply: dict[str, str] = Field(default_factory=dict)


class Quest(BaseModel):
    id: str
    title: str
    floor: int
    floor_name: str = ""
    neighborhood: str
    kind: QuestKind = "room"
    prerequisites: list[str] = Field(default_factory=list)
    level_required: int = 1
    exam_tasks: list[str] = Field(default_factory=list)
    stats: dict[str, int] = Field(default_factory=dict)
    brief: str
    starter: str = ""
    language: Literal["python", "usda", "none"] = "python"
    validator: dict[str, list[dict[str, Any]]] = Field(
        default_factory=lambda: {"assertions": []}
    )
    cookbook: str
    xp: int = 100
    reward: str | dict[str, Any] = ""
    world_target: str | None = None
    recipes: list[str] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)


class RunRequest(BaseModel):
    code: str = ""
    language: Literal["python", "usda", "none"] | None = None
    answers: list[int | str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    rule: str
    passed: bool
    message: str


class RunResponse(BaseModel):
    success: bool
    quest_id: str
    results: list[ValidationResult]
    output: str = ""
    system_message: str
    state: dict[str, Any]


class PlayerState(BaseModel):
    version: int = 1
    contestant: str = "USD-01"
    title: str = "Unlicensed Primwright"
    level: int = 1
    xp: int = 0
    opinion_points: int = 0
    completed_quests: list[str] = Field(default_factory=list)
    stats: dict[str, int] = Field(
        default_factory=lambda: {
            "Authoring": 0,
            "Composition": 0,
            "Aggregation": 0,
            "Debug": 0,
            "Pipeline": 0,
        }
    )
    inventory: dict[str, int] = Field(
        default_factory=lambda: {"hint_tokens": 2, "system_peeks": 1}
    )
    upgrades: list[str] = Field(default_factory=list)
    recipes: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    specialization: str | None = None

