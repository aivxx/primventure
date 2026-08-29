import os
import re
import shutil
from pathlib import Path

import yaml
from pxr import Usd

from primventure.models import PlayerState, Question, Quest, RunRequest
from primventure import runner as runner_module
from primventure.runner import QuestRunner
from primventure.scene import world_scene
from primventure.store import (
    WORLD_DIR,
    LessonStore,
    QuestStore,
    SaveStore,
    level_for_xp,
    newest_world_mtime,
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


def test_lesson_bullets_survive_a_colon() -> None:
    """An unquoted 'label: detail' bullet is valid YAML that parses as a dict.

    yaml.safe_load accepts it, so only a type check catches the mistake before
    Pydantic rejects the whole store and every room 500s.
    """
    mistyped: list[str] = []
    for path in sorted(Path(__file__).resolve().parents[2].joinpath("lessons").glob("*.y*ml")):
        raw = yaml.safe_load(path.read_text()) or {}
        records = raw.get("lessons", raw)
        for lesson in ([records] if isinstance(records, dict) else records) or []:
            for index, beat in enumerate(lesson.get("beats") or []):
                for point in beat.get("points") or []:
                    if not isinstance(point, str):
                        mistyped.append(f"{path.name} {lesson.get('source')} beat {index}: {point!r}")
    assert not mistyped, mistyped


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
    quests = {quest.id: quest for quest in QuestStore().all()}
    assert quest_view(quests["f0_nameplate"], PlayerState())["expects"] == [
        '/City.cityName is set to "Primventure"',
    ]
    assert quest_view(quests["f1_civic_record"], PlayerState())["expects"] == [
        '/City/PropertyWard carries kind metadata "group"',
        '/City/PropertyWard carries documentation metadata "Civic property district."',
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
    catalog = QuestStore().all()
    saves = SaveStore(tmp_path / "save.json")
    runner = QuestRunner(saves)

    # The city starts empty, so /City exists only once the opening room has
    # published it. Clearing that room is what this one's prerequisite means.
    opener = next(item for item in catalog if item.id == "f0_first_prim")
    opened = runner.run(
        opener,
        RunRequest(code=f'{opener.starter}stage.DefinePrim("/City", "Xform")\nstage.GetRootLayer().Save()\n'),
    )
    assert opened.success, [check.message for check in opened.results if not check.passed]

    quest = next(item for item in catalog if item.id == "f0_nameplate")
    unchanged = runner.run(quest, RunRequest(code=quest.starter))
    assert not unchanged.success
    assert [check.passed for check in unchanged.results] == [False]
    assert 'def Xform "City"' in unchanged.before_usda
    assert "cityName" not in unchanged.after_usda

    solution = quest.starter.replace(
        "stage.GetRootLayer().Save()",
        'attribute = city.CreateAttribute("cityName", Sdf.ValueTypeNames.String)\n'
        'attribute.Set("Primventure")\n'
        "stage.GetRootLayer().Save()",
    )
    solved = runner.run(quest, RunRequest(code=solution))
    assert solved.success, [check.message for check in solved.results if not check.passed]
    assert 'custom string cityName = "Primventure"' in solved.after_usda
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


def test_city_feed_goes_stale_when_any_published_layer_changes(tmp_path: Path) -> None:
    """Re-clearing a room rewrites its workstream layer and leaves root.usda alone."""
    world = tmp_path / "world"
    bundle = world / "workstreams" / "f0_first_prim"
    bundle.mkdir(parents=True)
    (world / ".preview").mkdir()

    root = world / "root.usda"
    root.write_text("#usda 1.0\n")
    os.utime(root, (1_000, 1_000))
    cache = world / ".preview" / "world.glb"
    cache.write_text("glb")
    os.utime(cache, (5_000, 5_000))
    assert newest_world_mtime(world) == 1_000

    submission = bundle / "submission.usd"
    submission.write_text("#usda 1.0\n")
    os.utime(submission, (9_000, 9_000))
    assert newest_world_mtime(world) == 9_000

    review = bundle / ".review" / "after.usda"
    review.parent.mkdir()
    review.write_text("#usda 1.0\n")
    os.utime(review, (20_000, 20_000))
    assert newest_world_mtime(world) == 9_000


def test_city_feed_stamp_survives_a_missing_world(tmp_path: Path) -> None:
    assert newest_world_mtime(tmp_path / "nothing-here") == 0.0


def test_city_feed_scene_carries_the_shapes_the_city_is_built_from(tmp_path: Path) -> None:
    """The districts are implicit Cube and Sphere gprims, which carry no points."""
    from pxr import Gf, UsdGeom

    root = tmp_path / "root.usda"
    stage = Usd.Stage.CreateNew(str(root))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.Xform.Define(stage, "/City")
    tower = UsdGeom.Cube.Define(stage, "/City/Tower")
    tower.GetSizeAttr().Set(3.0)
    tower.AddTranslateOp().Set(Gf.Vec3d(5, 0, 0))
    dome = UsdGeom.Sphere.Define(stage, "/City/Dome")
    dome.GetRadiusAttr().Set(2.0)
    dome.GetDisplayColorAttr().Set([Gf.Vec3f(1.0, 0.0, 0.0)])
    road = UsdGeom.Mesh.Define(stage, "/City/Road")
    road.GetPointsAttr().Set([Gf.Vec3f(0, 0, 0), Gf.Vec3f(1, 0, 0), Gf.Vec3f(1, 0, 1), Gf.Vec3f(0, 0, 1)])
    road.GetFaceVertexCountsAttr().Set([4])
    road.GetFaceVertexIndicesAttr().Set([0, 1, 2, 3])
    UsdGeom.Cube.Define(stage, "/City/Ghost").MakeInvisible()
    stage.GetRootLayer().Save()

    scene = world_scene(root)
    shapes = {prim["path"]: prim for prim in scene["prims"]}

    assert scene["up_axis"] == "Y"
    assert "/City/Ghost" not in shapes, "hidden prims should not reach the feed"
    assert shapes["/City/Tower"]["size"] == 3.0
    # USD writes a row-major matrix, so translation sits in the last row.
    assert shapes["/City/Tower"]["matrix"][12:15] == [5.0, 0.0, 0.0]
    assert shapes["/City/Dome"]["radius"] == 2.0
    assert shapes["/City/Dome"]["color"] == [1.0, 0.0, 0.0]
    assert len(shapes["/City/Road"]["points"]) == 4
    assert shapes["/City/Road"]["triangles"] == [0, 1, 2, 0, 2, 3], "quads need triangulating"


def test_city_feed_scene_grows_as_rooms_author_geometry(tmp_path: Path) -> None:
    root = tmp_path / "root.usda"
    stage = Usd.Stage.CreateNew(str(root))
    stage.GetRootLayer().Save()
    assert world_scene(root)["prims"] == []

    from pxr import UsdGeom

    UsdGeom.Cube.Define(stage, "/City/Kiosk")
    stage.GetRootLayer().Save()
    assert [prim["path"] for prim in world_scene(root)["prims"]] == ["/City/Kiosk"]


def test_city_feed_scene_is_empty_without_a_world(tmp_path: Path) -> None:
    assert world_scene(tmp_path / "missing.usda")["prims"] == []


# A room may only grade the player on an API the curriculum has already
# covered. Each validator demand lists the calls that can satisfy it.
AUTHORING_CALLS: dict[str, tuple[str, ...]] = {
    "prim_exists": ("DefinePrim", "OverridePrim"),
    "prim_type": ("DefinePrim",),
    "traversal_contains": ("DefinePrim",),
    "attribute_equals": ("CreateAttribute",),
    "metadata_equals": ("SetMetadata", "SetDocumentation", "SetAssetInfo", "SetKind"),
    "kind_equals": ("SetKind", "SetMetadata"),
    "active": ("SetActive",),
    "default_prim": ("SetDefaultPrim",),
    "up_axis": ("SetStageUpAxis",),
    "meters_per_unit": ("SetStageMetersPerUnit",),
    "start_time": ("SetStartTimeCode",),
    "end_time": ("SetEndTimeCode",),
    "sublayer_order": ("subLayerPaths",),
    "has_reference": ("AddReference",),
    "has_payload": ("AddPayload",),
    "has_inherit": ("AddInherit",),
    "has_specializes": ("AddSpecialize",),
    "has_variant_set": ("AddVariantSet",),
    "instanceable": ("SetInstanceable",),
    "point_instancer": ("PointInstancer",),
    "layer_offset": ("LayerOffset",),
}
# One demand, three constructors.
SPECIFIER_CALLS = {
    "def": ("DefinePrim",),
    "over": ("OverridePrim",),
    "class": ("CreateClassPrim",),
}
# These read the composed result instead of asking for another call.
INSPECTION_ONLY = {"attribute_source", "prim_stack"}


def _lesson_body(lesson) -> str:
    parts: list[str] = []
    for beat in lesson.beats:
        parts += [beat.heading or "", beat.body or "", beat.code or ""]
        parts += list(beat.points or [])
    return "\n".join(parts)


def _calls_for(kind: str, payload) -> tuple[str, ...]:
    if kind == "specifier_equals":
        value = payload.get("value") if isinstance(payload, dict) else payload
        return SPECIFIER_CALLS[str(value)]
    return AUTHORING_CALLS.get(kind, ())


def test_no_room_grades_an_api_the_lessons_have_not_taught_yet() -> None:
    """Rooms are exercises, not guessing games about APIs still floors away.

    A demand is fair once a lesson the player has already read shows the call,
    or once the terminal types it out for them.
    """
    store = QuestStore()
    lessons = store.lessons.all()
    taught = ""
    unfair: list[str] = []
    for quest in store.all():
        lesson = lessons.get(quest.cookbook)
        if lesson is not None:
            taught += "\n" + _lesson_body(lesson)
        for rule in quest.validator.get("assertions", []):
            for kind, payload in rule.items():
                if kind in INSPECTION_ONLY:
                    continue
                calls = _calls_for(kind, payload)
                if any(call in quest.starter for call in calls):
                    continue
                if not any(call in taught for call in calls):
                    unfair.append(
                        f"{quest.id} grades {kind} before any lesson teaches "
                        f"{' or '.join(calls)}"
                    )
    assert not unfair, unfair


def test_every_assertion_kind_names_the_call_it_grades() -> None:
    """A new rule has to declare its API, or the audit above quietly goes blind."""
    known = set(AUTHORING_CALLS) | INSPECTION_ONLY | {"specifier_equals"}
    used = {
        kind
        for quest in QuestStore().all()
        for rule in quest.validator.get("assertions", [])
        for kind in rule
    }
    assert used <= known, used - known

