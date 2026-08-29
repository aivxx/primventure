import re
import shutil
from pathlib import Path

from primventure.models import PlayerState, Question, Quest, RunRequest
from primventure import runner as runner_module
from primventure.runner import QuestRunner
from primventure.store import (
    WORLD_DIR,
    LessonStore,
    QuestStore,
    SaveStore,
    level_for_xp,
    quest_view,
    space_out_steps,
    with_save_line,
)


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


def test_edited_lesson_cards_reload_without_a_restart(tmp_path: Path) -> None:
    lessons = tmp_path / "lessons"
    lessons.mkdir()
    card = lessons / "prims.yaml"
    body = """
source: docs/prims.md
title: Prims
objective: Identify what a prim is.
intro: Welcome to the part where empty boxes get addresses.
beats:
  - kind: concept
    heading: A prim is a container
    body: {body}
apply:
  first_prim: Define /City.
"""
    card.write_text(body.format(body="Schema types expose GetXxxAttr methods."))
    store = LessonStore(lessons)
    assert "GetXxxAttr" in store.resolve("docs/prims.md", "first_prim")["beats"][0]["body"]

    card.write_text(body.format(body="Each schema-specific API grabs its own attributes."))
    store.refresh()
    assert "schema-specific" in store.resolve("docs/prims.md", "first_prim")["beats"][0]["body"]


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


def test_every_python_terminal_ships_the_save_line() -> None:
    for quest in QuestStore().all():
        if quest.language != "python":
            continue
        assert "Save(" in quest.starter or "Export(" in quest.starter, quest.id


def test_save_line_is_only_added_where_it_makes_sense() -> None:
    assert with_save_line("stage = Usd.Stage.Open(STAGE_PATH)\n", "python").endswith(
        "stage.GetRootLayer().Save()\n"
    )
    # Rooms that already persist, hand-author USDA, or never open a stage are untouched.
    already = "stage.GetRootLayer().Save()\n"
    assert with_save_line(already, "python") == already
    exports = "stage.Flatten().Export(STAGE_PATH)\n"
    assert with_save_line(exports, "python") == exports
    usda = "#usda 1.0\n"
    assert with_save_line(usda, "usda") == usda
    layer_only = "layer = Sdf.Layer.CreateNew(STAGE_PATH)\n"
    assert with_save_line(layer_only, "python") == layer_only
    assert with_save_line("", "python") == ""


def test_numbered_steps_get_room_to_type_under() -> None:
    starter = (
        "stage = Usd.Stage.Open(STAGE_PATH)\n"
        "# 1. Author the attribute.\n"
        "#    The wrapped half of step one.\n"
        "# 2. Author the metadata.\n"
        "stage.GetRootLayer().Save()\n"
    )
    assert space_out_steps(starter, "python") == (
        "stage = Usd.Stage.Open(STAGE_PATH)\n"
        "\n"
        "# 1. Author the attribute.\n"
        "#    The wrapped half of step one.\n"
        "\n"
        "# 2. Author the metadata.\n"
        "\n"
        "stage.GetRootLayer().Save()\n"
    )


def test_spacing_leaves_headers_and_existing_gaps_alone() -> None:
    header = '#usda 1.0\n(\n    defaultPrim = "City"\n)\n'
    assert space_out_steps(header, "usda") == header
    already_spaced = "# Author it.\n\nstage.GetRootLayer().Save()\n"
    assert space_out_steps(already_spaced, "python") == already_spaced
    assert space_out_steps("", "python") == ""


def test_authored_starters_stay_parseable_after_normalization() -> None:
    import ast

    from pxr import Sdf

    for quest in QuestStore().all():
        if quest.language == "python":
            ast.parse(quest.starter)
        elif quest.language == "usda":
            layer = Sdf.Layer.CreateAnonymous(".usda")
            assert layer.ImportFromString(quest.starter), quest.id


def test_run_returns_the_same_state_shape_as_the_state_endpoint(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from primventure import api as api_module

    monkeypatch.setattr(api_module, "saves", SaveStore(tmp_path / "save.json"))
    client = TestClient(api_module.app)
    baseline = client.get("/api/state").json()
    run = client.post("/api/quests/f0_first_prim/run", json={"code": "", "language": "python"}).json()
    assert set(run["state"]) == set(baseline)


def test_every_validated_room_states_what_the_terminal_checks() -> None:
    quests = QuestStore().all()
    for quest in quests:
        assertions = quest.validator.get("assertions", [])
        expects = quest_view(quest, PlayerState())["expects"]
        assert len(expects) == len(assertions), quest.id
        for line in expects:
            # The fallback wording means a rule shipped without a description.
            assert "holds for" not in line, f"{quest.id}: {line}"
            assert line.strip()


def test_expectations_name_the_exact_value_the_validator_wants() -> None:
    nameplate = next(quest for quest in QuestStore().all() if quest.id == "f0_nameplate")
    expects = quest_view(nameplate, PlayerState())["expects"]
    assert expects == [
        '/City.cityName is set to "Primventure"',
        '/City carries documentation metadata "The persistent city portfolio."',
    ]


def test_quest_view_advertises_the_payout_the_runner_awards(tmp_path: Path) -> None:
    room = Quest(
        id="room",
        title="Room",
        floor=0,
        neighborhood="Block",
        brief="Author.",
        cookbook="docs/index.md",
    )
    boss = Quest(
        id="boss",
        title="Boss",
        kind="floor_boss",
        floor=0,
        neighborhood="Block",
        brief="Synthesize.",
        cookbook="docs/index.md",
    )
    payer = Quest(
        id="payer",
        title="Payer",
        kind="orientation",
        floor=0,
        neighborhood="Intake",
        brief="Welcome.",
        language="none",
        cookbook="docs/index.md",
        reward={"opinion_points": 3},
    )
    assert quest_view(room, PlayerState())["opinion_points"] == 0
    assert quest_view(boss, PlayerState())["opinion_points"] == 1

    advertised = quest_view(payer, PlayerState())["opinion_points"]
    saves = SaveStore(tmp_path / "save.json")
    result = QuestRunner(saves).run(payer, RunRequest())
    assert result.success
    assert saves.load().opinion_points == advertised == 3


def test_nameplate_room_is_solvable_from_what_the_ui_states(
    tmp_path: Path, monkeypatch
) -> None:
    """The checklist is the only place the exact strings appear, so it has to be enough."""
    world = tmp_path / "world"
    world.mkdir()
    shutil.copy(WORLD_DIR / "root.usda", world / "root.usda")
    monkeypatch.setattr(runner_module, "WORLD_DIR", world)
    quest = next(item for item in QuestStore().all() if item.id == "f0_nameplate")
    saves = SaveStore(tmp_path / "save.json")
    saves.save(PlayerState(completed_quests=["f0_first_prim"]))
    runner = QuestRunner(saves)

    unchanged = runner.run(quest, RunRequest(code=quest.starter))
    assert not unchanged.success
    assert [check.passed for check in unchanged.results] == [False, False]
    assert 'def Xform "City"' in unchanged.before_usda
    assert "cityName" not in unchanged.after_usda

    solution = quest.starter.replace(
        "stage.GetRootLayer().Save()",
        'attribute = city.CreateAttribute("cityName", Sdf.ValueTypeNames.String)\n'
        'attribute.Set("Primventure")\n'
        'city.SetMetadata("documentation", "The persistent city portfolio.")\n'
        "stage.GetRootLayer().Save()",
    )
    solved = runner.run(quest, RunRequest(code=solution))
    assert solved.success, [check.message for check in solved.results if not check.passed]
    assert 'custom string cityName = "Primventure"' in solved.after_usda
    assert 'doc = "The persistent city portfolio."' in solved.after_usda
    review = runner.usda_view(quest)
    assert review["before_usda"] == solved.before_usda
    assert review["after_usda"] == solved.after_usda


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

