from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import yaml

from .models import PlayerState, Quest


ROOT = Path(__file__).resolve().parents[3]
GAME_DIR = ROOT / "game"
QUEST_DIR = GAME_DIR / "quests"
SAVE_PATH = GAME_DIR / "save.json"
WORLD_DIR = ROOT / "world"


class QuestStore:
    def __init__(self, quest_dir: Path = QUEST_DIR):
        self.quest_dir = quest_dir
        self._quests: dict[str, Quest] = {}
        self.reload()

    def reload(self) -> None:
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
            return PlayerState.model_validate_json(self.path.read_text())

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


def quest_view(quest: Quest, state: PlayerState) -> dict[str, Any]:
    data = quest.model_dump(exclude={"validator"})
    data["questions"] = [
        {"prompt": question.prompt, "choices": question.choices}
        for question in quest.questions
    ]
    prereqs_met = all(item in state.completed_quests for item in quest.prerequisites)
    data["unlocked"] = prereqs_met and state.level >= quest.level_required
    data["completed"] = quest.id in state.completed_quests
    return data

