from __future__ import annotations

import json
import os
import re
import shutil
import threading
from pathlib import Path
from typing import Any

import yaml

from .expectations import describe_assertions
from .benefits import (
    free_assist_available,
    home_boss_bonus,
    is_home_floor,
    preview_boss_fee,
)
from .models import LessonCard, PlayerState, Quest


ROOT = Path(__file__).resolve().parents[3]
GAME_DIR = ROOT / "game"
QUEST_DIR = GAME_DIR / "quests"
LESSON_DIR = GAME_DIR / "lessons"
SAVE_PATH = GAME_DIR / "save.json"
# The tracked world/ is a template: quest assets, the reference gallery, and an
# unplayed root layer. Publishing into it would put a player's city in git, so
# play happens inside a copy that git ignores.
WORLD_TEMPLATE = ROOT / "world"
STATE_DIR = Path(os.environ.get("PRIMVENTURE_STATE_DIR") or ROOT / ".primventure")
WORLD_DIR = STATE_DIR / "world"


SAVE_LINE = "stage.GetRootLayer().Save()"
STEP_COMMENT = re.compile(r"^\s*#\s*\d+[.)]\s")


def space_out_steps(starter: str, language: str) -> str:
    """Leave a blank line under every instruction so there is somewhere to type.

    Consecutive comment lines are one instruction unless the next one opens a
    numbered step, which keeps wrapped explanations attached to their step.
    """
    if language == "none" or not starter.strip():
        return starter
    lines = starter.rstrip("\n").split("\n")
    spaced: list[str] = []
    for index, line in enumerate(lines):
        following = lines[index + 1] if index + 1 < len(lines) else None
        # `#usda 1.0` is a file header, not an instruction to write under.
        is_comment = line.lstrip().startswith("#") and not line.lstrip().startswith("#usda")
        if is_comment and spaced and spaced[-1].strip() and not spaced[-1].lstrip().startswith("#"):
            spaced.append("")
        spaced.append(line)
        if not is_comment or following is None or not following.strip():
            continue
        continues_block = following.lstrip().startswith("#") and not STEP_COMMENT.match(following)
        if not continues_block:
            spaced.append("")
    return "\n".join(spaced) + "\n"


def with_save_line(starter: str, language: str) -> str:
    """Persisting the stage is plumbing, not the lesson, so the terminal ships it.

    Rooms that already save, write their own layer, or hand-author USDA are left
    exactly as their author wrote them.
    """
    if language != "python" or not starter.strip():
        return starter
    if "Save(" in starter or "Export(" in starter:
        return starter
    if "stage" not in starter:
        return starter
    return starter.rstrip("\n") + "\n" + SAVE_LINE + "\n"


def normalize_starter(starter: str, language: str) -> str:
    return space_out_steps(with_save_line(starter, language), language)


def opinion_points_for(quest: Quest, state: PlayerState | None = None) -> int:
    """Boss rooms pay by default, and any room can override it in its reward."""
    reward = quest.reward if isinstance(quest.reward, dict) else {}
    base = int(reward.get("opinion_points", 1 if quest.kind.endswith("boss") else 0))
    if state is None:
        return base
    return base + home_boss_bonus(state.specialization, quest)


def seed_world(target: Path, template: Path = WORLD_TEMPLATE) -> Path:
    """Give play a writable city, copied out of the tracked template.

    Only a missing target is seeded. A player's published city and the layers it
    sublayers in live here, so re-copying the template would demolish the run.
    """
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    if template.exists():
        shutil.copytree(template, target, ignore=shutil.ignore_patterns(".*"))
    else:
        target.mkdir(parents=True)
    return target


def newest_world_mtime(world_dir: Path = WORLD_DIR) -> float:
    """When the composed city last changed.

    The stage is the root layer plus every layer it sublayers in, so a room that
    republishes an existing workstream changes the city without touching
    root.usda. Dot-directories hold caches and review snapshots, not scene
    description, so they are ignored.
    """
    newest = 0.0
    if not world_dir.exists():
        return newest
    for path in world_dir.rglob("*"):
        if not path.is_file():
            continue
        if any(part.startswith(".") for part in path.relative_to(world_dir).parts):
            continue
        newest = max(newest, path.stat().st_mtime)
    return newest


def content_stamp(directory: Path, recursive: bool = False) -> tuple[tuple[str, int, int], ...]:
    """Identity of a content directory, so edited YAML can be noticed on the fly."""
    if not directory.exists():
        return ()
    paths = directory.rglob("*.y*ml") if recursive else directory.glob("*.y*ml")
    stamped = []
    for path in sorted(paths):
        stat = path.stat()
        # Size joins mtime because edits saved inside one filesystem clock tick
        # would otherwise look unchanged.
        stamped.append((str(path), stat.st_mtime_ns, stat.st_size))
    return tuple(stamped)


class LessonStore:
    def __init__(self, lesson_dir: Path = LESSON_DIR):
        self.lesson_dir = lesson_dir
        self._lessons: dict[str, LessonCard] = {}
        self._stamp: tuple[tuple[str, int, int], ...] = ()
        self._lock = threading.Lock()
        self.reload()

    def refresh(self) -> None:
        with self._lock:
            if content_stamp(self.lesson_dir, recursive=True) != self._stamp:
                self.reload()

    def reload(self) -> None:
        self._stamp = content_stamp(self.lesson_dir, recursive=True)
        lessons: dict[str, LessonCard] = {}
        if self.lesson_dir.exists():
            for path in sorted(self.lesson_dir.rglob("*.y*ml")):
                raw = yaml.safe_load(path.read_text()) or {}
                records = raw.get("lessons", raw) if isinstance(raw, dict) else raw
                if isinstance(records, dict):
                    records = [records]
                for record in records or []:
                    lesson = LessonCard.model_validate(record)
                    if lesson.source in lessons:
                        raise ValueError(f"Duplicate lesson source {lesson.source!r}")
                    lessons[lesson.source] = lesson
        self._lessons = lessons

    def all(self) -> dict[str, LessonCard]:
        return dict(self._lessons)

    def resolve(self, source: str, quest_id: str) -> dict[str, Any] | None:
        lesson = self._lessons.get(source)
        if lesson is None:
            return None
        data = lesson.model_dump(exclude={"apply"})
        data["apply"] = lesson.apply.get(quest_id, "")
        return data


class QuestStore:
    def __init__(self, quest_dir: Path = QUEST_DIR, lesson_dir: Path | None = None):
        self.quest_dir = quest_dir
        if lesson_dir is None:
            lesson_dir = LESSON_DIR if quest_dir == QUEST_DIR else quest_dir.parent / "lessons"
        self.lessons = LessonStore(lesson_dir)
        self._quests: dict[str, Quest] = {}
        self._stamp: tuple[tuple[str, int, int], ...] = ()
        self._lock = threading.Lock()
        self.reload()

    def refresh(self) -> None:
        """Pick up authored rooms and lesson cards without restarting the server."""
        with self._lock:
            if content_stamp(self.quest_dir) != self._stamp:
                self.reload()
        self.lessons.refresh()

    def reload(self) -> None:
        self._stamp = content_stamp(self.quest_dir)
        quests: dict[str, Quest] = {}
        if self.quest_dir.exists():
            for path in sorted(self.quest_dir.glob("*.y*ml")):
                raw = yaml.safe_load(path.read_text()) or {}
                records = raw.get("quests", raw) if isinstance(raw, dict) else raw
                if isinstance(records, dict):
                    records = [records]
                for record in records or []:
                    quest = Quest.model_validate(record)
                    if quest.id in quests:
                        raise ValueError(f"Duplicate quest id {quest.id!r}")
                    quest.starter = normalize_starter(quest.starter, quest.language)
                    quests[quest.id] = quest
        self._quests = quests

    def all(self) -> list[Quest]:
        # Stable sort keeps each floor file's authored order, which is the
        # prerequisite chain the dungeon map draws as a route.
        return sorted(self._quests.values(), key=lambda q: q.floor)

    def get(self, quest_id: str) -> Quest:
        try:
            return self._quests[quest_id]
        except KeyError as exc:
            raise KeyError(f"Unknown quest {quest_id!r}") from exc

    def lesson_for(self, quest: Quest) -> dict[str, Any] | None:
        return self.lessons.resolve(quest.cookbook, quest.id)


def migrate(raw: dict[str, Any]) -> dict[str, Any]:
    """Carry older saves onto the current consumable.

    Opinion X-Rays became Inspector's Slips and then the Prim Census. Stock,
    home-floor claims, and the repeatable shop entry all move across so a save
    in flight neither loses supplies nor earns a second free use.
    """
    inventory = raw.setdefault("inventory", {})
    for retired in ("system_peeks", "inspectors_slips"):
        if retired in inventory:
            inventory["prim_censuses"] = inventory.get("prim_censuses", 0) + inventory.pop(retired)
    claims = raw.get("benefit_claims") or {}
    for key in [key for key in claims if key.startswith("free_peek:")]:
        claims[f"free_census:{key.split(':', 1)[1]}"] = claims.pop(key)
    raw["upgrades"] = [
        "prim_census" if entry == "system_peek" else entry for entry in raw.get("upgrades") or []
    ]
    # A fail recorded by the retired diagnosis carried no census. Only that
    # shape is dropped; discarding a current one would erase the stage reading
    # on every load and leave the census permanently unarmed.
    fail = raw.get("last_fail")
    if isinstance(fail, dict) and "has_stage" not in fail:
        raw.pop("last_fail")
    return raw


class SaveStore:
    def __init__(self, path: Path = SAVE_PATH):
        self.path = path
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> PlayerState:
        with self._lock:
            if not self.path.exists():
                state = PlayerState()
                self._write(state)
                return state
            return PlayerState.model_validate(migrate(json.loads(self.path.read_text())))

    def save(self, state: PlayerState) -> PlayerState:
        with self._lock:
            self._write(state)
        return state

    def reset(self) -> PlayerState:
        return self.save(PlayerState())

    def _write(self, state: PlayerState) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(state.model_dump_json(indent=2) + "\n")
        temporary.replace(self.path)


def level_for_xp(xp: int) -> int:
    # Content is the gate; levels are a generous secondary reward signal.
    return 1 + xp // 100


def xp_holding_level(xp: int) -> int:
    """The XP a player may lose before the curve demotes them."""
    return xp - (level_for_xp(xp) - 1) * 100


def quest_view(
    quest: Quest,
    state: PlayerState,
    lesson: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = quest.model_dump(exclude={"validator"})
    data["questions"] = [
        {"prompt": question.prompt, "choices": question.choices}
        for question in quest.questions
    ]
    prereqs_met = all(item in state.completed_quests for item in quest.prerequisites)
    data["unlocked"] = prereqs_met and state.level >= quest.level_required
    data["completed"] = quest.id in state.completed_quests
    data["opinion_points"] = opinion_points_for(quest, state)
    data["home_floor"] = is_home_floor(state.specialization, quest.floor)
    fee, fee_kind = preview_boss_fee(state, quest)
    data["boss_fee"] = fee
    data["boss_fee_kind"] = fee_kind
    data["free_hint"] = free_assist_available(state, quest, "hint")
    data["free_census"] = free_assist_available(state, quest, "census")
    fail = state.last_fail
    # A census reads a stage, so a run that never produced one cannot be sold.
    armed = (
        fail is not None
        and fail.quest_id == quest.id
        and quest.id not in state.completed_quests
        and fail.has_stage
    )
    data["census_armed"] = armed
    data["census_paid"] = bool(armed and fail and fail.paid)
    data["expects"] = describe_assertions(quest.validator)
    data["lesson"] = lesson
    data["submission"] = state.submissions.get(quest.id, "")
    return data

