import re
from pathlib import Path

from primventure.models import PlayerState, Question, Quest, RunRequest
from primventure import runner as runner_module
from primventure.runner import QuestRunner
from primventure.store import LessonStore, QuestStore, SaveStore, level_for_xp, quest_view


def test_level_curve_is_generous() -> None:
    assert level_for_xp(0) == 1
    assert level_for_xp(99) == 1
    assert level_for_xp(100) == 2


def test_quest_store_loads_catalog(tmp_path: Path) -> None:
    (tmp_path / "floor.yaml").write_text(
        """
quests:
  - id: orientation
    title: Begin
    floor: 0
    neighborhood: Intake
    kind: orientation
    brief: Listen to the System.
    language: none
    cookbook: docs/what-openusd/index.md
"""
    )
    quests = QuestStore(tmp_path).all()
    assert [quest.id for quest in quests] == ["orientation"]


def test_catalog_order_is_a_playable_route() -> None:
    quests = QuestStore().all()
    assert [quest.floor for quest in quests] == sorted(quest.floor for quest in quests)
    cleared: set[str] = set()
    for quest in quests:
        missing = [item for item in quest.prerequisites if item not in cleared]
        assert not missing, f"{quest.id} is listed before {missing}"
        cleared.add(quest.id)


def test_lesson_store_resolves_room_specific_apply(tmp_path: Path) -> None:
    (tmp_path / "prims.yaml").write_text(
        """
source: docs/prims.md
title: Prims
objective: Identify what a prim is.
intro: Welcome to the part where empty boxes get addresses.
beats:
  - kind: concept
    heading: A prim is a container
    system: Unglamorous, like the badge I printed for you.
    body: A prim has a path.
    points:
      - Paths are unique.
apply:
  first_prim: Define /City.
"""
    )
    lesson = LessonStore(tmp_path).resolve("docs/prims.md", "first_prim")
    assert lesson == {
        "source": "docs/prims.md",
        "title": "Prims",
        "objective": "Identify what a prim is.",
        "intro": "Welcome to the part where empty boxes get addresses.",
        "beats": [
            {
                "kind": "concept",
                "heading": "A prim is a container",
                "system": "Unglamorous, like the badge I printed for you.",
                "body": "A prim has a path.",
                "points": ["Paths are unique."],
                "code": "",
            }
        ],
        "apply": "Define /City.",
    }


def test_every_quest_has_a_resolved_lesson() -> None:
    store = QuestStore()
    missing = [
        quest.id
        for quest in store.all()
        if not (store.lesson_for(quest) or {}).get("apply")
    ]
    assert not missing


def test_lessons_teach_in_depth() -> None:
    """Cards must stand alone, so shallow ones are a regression, not a style choice."""
    thin: list[str] = []
    for source, lesson in QuestStore().lessons.all().items():
        kinds = [beat.kind for beat in lesson.beats]
        prose = sum(
            len(beat.body) + sum(len(point) for point in beat.points)
            for beat in lesson.beats
        )
        if (
            len(lesson.beats) < 4
            or kinds[-1] != "recap"
            or "pitfall" not in kinds
            or not any(beat.code for beat in lesson.beats)
            or prose < 1200
        ):
            thin.append(source)
    assert not thin


def test_system_voice_stays_in_its_own_fields() -> None:
    """The UI labels the speaker, so narration must not leak into teaching copy."""
    leaks: list[str] = []
    for source, lesson in QuestStore().lessons.all().items():
        if not lesson.intro or not lesson.objective:
            leaks.append(source)
            continue
        teaching = [lesson.objective, *(beat.body for beat in lesson.beats)]
        teaching += [point for beat in lesson.beats for point in beat.points]
        if any(re.search(r"\bSYSTEM\s*:|\bThe System\b", text) for text in teaching):
            leaks.append(source)
    assert not leaks


def test_orientation_awards_only_once(tmp_path: Path) -> None:
    saves = SaveStore(tmp_path / "save.json")
    runner = QuestRunner(saves)
    quest = Quest(
        id="orientation",
        title="Begin",
        floor=0,
        neighborhood="Intake",
        kind="orientation",
        brief="Welcome.",
        language="none",
        cookbook="docs/what-openusd/index.md",
        xp=100,
        recipes=["Prim"],
    )
    assert runner.run(quest, RunRequest()).success
    assert runner.run(quest, RunRequest()).success
    state = saves.load()
    assert state.xp == 100
    assert state.recipes == ["Prim"]


def test_quest_view_does_not_leak_answers() -> None:
    quest = Quest(
        id="boss",
        title="Boss",
        floor=9,
        neighborhood="Arena",
        brief="Answer.",
        cookbook="docs/index.md",
        questions=[Question(prompt="Why?", answer_key="Because composition is stronger.")],
    )
    public = quest_view(quest, PlayerState())
    assert public["questions"] == [{"prompt": "Why?", "choices": []}]
    assert public["lesson"] is None


def test_publish_preserves_supporting_layers(
    tmp_path: Path, monkeypatch
) -> None:
    world = tmp_path / "world"
    world.mkdir()
    (world / "root.usda").write_text("#usda 1.0\n")
    arena = tmp_path / "arena"
    arena.mkdir()
    artifact = arena / "submission.usd"
    artifact.write_text("#usda 1.0\n")
    (arena / "weaker.usda").write_text("#usda 1.0\n")
    monkeypatch.setattr(runner_module, "WORLD_DIR", world)
    quest = Quest(
        id="layer-boss",
        title="Layer Boss",
        floor=3,
        neighborhood="Layers",
        brief="Compose.",
        cookbook="docs/index.md",
    )

    QuestRunner(SaveStore(tmp_path / "save.json"))._publish(quest, artifact)

    bundle = world / "workstreams" / "layer-boss"
    assert (bundle / "submission.usd").exists()
    assert (bundle / "weaker.usda").exists()
    assert "workstreams/layer-boss/submission.usd" in (
        world / "root.usda"
    ).read_text()

