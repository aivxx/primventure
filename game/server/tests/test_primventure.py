from pathlib import Path

from primventure.models import PlayerState, Question, Quest, RunRequest
from primventure import runner as runner_module
from primventure.runner import QuestRunner
from primventure.store import QuestStore, SaveStore, level_for_xp, quest_view


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

