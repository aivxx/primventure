from pathlib import Path

from fastapi.testclient import TestClient
from pxr import Sdf, Usd

from primventure import runner as runner_module
from primventure.census import observe
from primventure.models import PlayerState
from primventure.runner import QuestRunner
from primventure.store import QuestStore, SaveStore, migrate
from primventure.usd_check import successful_usda


EMPTY_STAGE = """
from pxr import Usd
stage = Usd.Stage.CreateNew(STAGE_PATH)
stage.GetRootLayer().Save()
"""

BRIDGE_MISSING_ITS_ORIGIN = """
from pxr import Usd
stage = Usd.Stage.CreateNew(STAGE_PATH)
bridge = stage.DefinePrim("/City/PropertyWard/Bridge", "Xform")
stage.DefinePrim("/City/PropertyWard/LampGlobe", "Sphere")
stage.DefinePrim("/City/PropertyWard/Canal", "Xform")
bridge.CreateRelationship("destination").SetTargets(
    ["/City/PropertyWard/LampGlobe"]
)
stage.GetRootLayer().Save()
"""


def _client(tmp_path: Path, monkeypatch, **state) -> tuple[TestClient, SaveStore]:
    from primventure import api as api_module

    world = tmp_path / "world"
    world.mkdir()
    store = SaveStore(tmp_path / "save.json")
    monkeypatch.setattr(api_module, "WORLD_DIR", world)
    monkeypatch.setattr(runner_module, "WORLD_DIR", world)
    monkeypatch.setattr(api_module, "saves", store)
    monkeypatch.setattr(api_module, "runner", QuestRunner(store))
    # The stage briefing opens the crawl, so the first authoring room sits behind it.
    defaults = dict(opinion_points=2, completed_quests=["f0_stage_intake"])
    defaults.update(state)
    store.save(PlayerState(**defaults))
    return TestClient(api_module.app), store


def _run(client: TestClient, quest: str, code: str, answers: list[int] | None = None) -> dict:
    return client.post(
        f"/api/quests/{quest}/run",
        json={"code": code, "language": "python", "answers": answers or []},
    ).json()


def test_usd_check_requires_a_failed_room(tmp_path: Path, monkeypatch) -> None:
    client, _ = _client(tmp_path, monkeypatch)

    denied = client.post("/api/quests/f0_first_prim/usd-check")

    assert denied.status_code == 409
    assert "Fail this room" in denied.json()["detail"]
    assert client.get("/api/state").json()["opinion_points"] == 2


def test_usd_check_costs_one_stocked_check_and_shows_successful_graded_usda(
    tmp_path: Path, monkeypatch
) -> None:
    client, _ = _client(
        tmp_path,
        monkeypatch,
        xp=500,
        level=6,
        completed_quests=["f1_binding_canal"],
    )
    failed = _run(client, "f2_relationship_bridge", BRIDGE_MISSING_ITS_ORIGIN)
    assert failed["success"] is False
    assert client.get("/api/quests/f2_relationship_bridge").json()["check_armed"] is True

    checked = client.post("/api/quests/f2_relationship_bridge/usd-check")

    assert checked.status_code == 200
    payload = checked.json()
    assert payload["state"]["opinion_points"] == 2
    assert payload["state"]["inventory"]["usd_checks"] == 1
    assert "rel destination" in payload["usda"]
    assert "rel origin" in payload["usda"]
    assert "</City/PropertyWard/LampGlobe>" in payload["usda"]
    assert "</City/PropertyWard/Canal>" in payload["usda"]
    layer = Sdf.Layer.CreateAnonymous(".usda")
    assert layer.ImportFromString(payload["usda"])


def test_a_paid_check_is_free_to_reread_but_a_new_fail_costs_again(
    tmp_path: Path, monkeypatch
) -> None:
    client, _ = _client(tmp_path, monkeypatch)
    assert _run(client, "f0_first_prim", EMPTY_STAGE)["success"] is False
    first = client.post("/api/quests/f0_first_prim/usd-check").json()
    second = client.post("/api/quests/f0_first_prim/usd-check").json()
    assert first["state"]["inventory"]["usd_checks"] == second["state"]["inventory"]["usd_checks"] == 1
    assert first["state"]["opinion_points"] == second["state"]["opinion_points"] == 2
    assert first["usda"] == second["usda"]

    assert _run(client, "f0_first_prim", EMPTY_STAGE)["success"] is False
    assert client.get("/api/quests/f0_first_prim").json()["check_paid"] is False
    third = client.post("/api/quests/f0_first_prim/usd-check").json()
    assert third["state"]["inventory"]["usd_checks"] == 0
    assert third["state"]["opinion_points"] == 2


def test_usd_check_refuses_at_zero_stock(tmp_path: Path, monkeypatch) -> None:
    client, _ = _client(
        tmp_path, monkeypatch, opinion_points=4, inventory={"hint_tokens": 2, "usd_checks": 0}
    )
    assert _run(client, "f0_first_prim", EMPTY_STAGE)["success"] is False

    denied = client.post("/api/quests/f0_first_prim/usd-check")

    assert denied.status_code == 409
    assert "No USD Checks remain" in denied.json()["detail"]
    assert client.get("/api/state").json()["opinion_points"] == 4


def test_a_syntax_error_still_unlocks_the_target_reference(
    tmp_path: Path, monkeypatch
) -> None:
    client, _ = _client(tmp_path, monkeypatch)
    assert _run(client, "f0_first_prim", "this is not python(")["success"] is False

    checked = client.post("/api/quests/f0_first_prim/usd-check")

    assert checked.status_code == 200
    assert 'def Xform "City"' in checked.json()["usda"]


def test_briefing_only_rooms_have_no_usda_check(tmp_path: Path, monkeypatch) -> None:
    client, _ = _client(
        tmp_path,
        monkeypatch,
        xp=900,
        level=10,
        completed_quests=["f4_kind_post"],
    )
    failed = _run(client, "f4_hydra_lecture", "", answers=[1])
    assert failed["success"] is False

    denied = client.post("/api/quests/f4_hydra_lecture/usd-check")

    assert denied.status_code == 409
    assert "no graded USDA" in denied.json()["detail"]


def test_compositor_gets_one_free_home_floor_check(
    tmp_path: Path, monkeypatch
) -> None:
    client, store = _client(
        tmp_path,
        monkeypatch,
        xp=600,
        level=7,
        opinion_points=0,
        inventory={"hint_tokens": 2, "usd_checks": 0},
        specialization="Compositor",
        completed_quests=["f2_blueprint_marshal"],
        benefit_claims={"starter_kit": True},
    )
    assert _run(client, "f3_layer_registry", EMPTY_STAGE)["success"] is False
    room = client.get("/api/quests/f3_layer_registry").json()
    assert room["free_check"] is True

    free = client.post("/api/quests/f3_layer_registry/usd-check")

    assert free.status_code == 200
    assert free.json()["state"]["opinion_points"] == 0
    assert store.load().benefit_claims["free_check:3"] is True

    assert _run(client, "f3_layer_registry", EMPTY_STAGE)["success"] is False
    denied = client.post("/api/quests/f3_layer_registry/usd-check")
    assert denied.status_code == 409


def test_cleared_room_does_not_sell_a_reference(tmp_path: Path, monkeypatch) -> None:
    client, _ = _client(tmp_path, monkeypatch, completed_quests=["f0_first_prim"])

    denied = client.post("/api/quests/f0_first_prim/usd-check")

    assert denied.status_code == 409
    assert "accepted USDA" in denied.json()["detail"]


def test_old_census_stock_refunds_op_and_preserves_claims() -> None:
    migrated = migrate(
        {
            "opinion_points": 2,
            "inventory": {
                "prim_censuses": 3,
                "system_peeks": 1,
                "inspectors_slips": 2,
            },
            "benefit_claims": {"free_peek:3": True, "free_census:5": True},
            "upgrades": ["system_peek", "prim_census", "deeper_hints"],
        }
    )

    assert migrated["opinion_points"] == 8
    assert migrated["inventory"]["usd_checks"] == 2
    assert "prim_censuses" not in migrated["inventory"]
    assert "system_peeks" not in migrated["inventory"]
    assert "inspectors_slips" not in migrated["inventory"]
    assert migrated["benefit_claims"] == {"free_check:3": True, "free_check:5": True}
    assert migrated["upgrades"] == ["deeper_hints"]


def test_every_authoring_room_generates_parseable_focused_usda() -> None:
    generated = 0
    for quest in QuestStore().all():
        if not quest.validator.get("assertions"):
            continue
        text = successful_usda(quest)
        layer = Sdf.Layer.CreateAnonymous(".usda")
        assert layer.ImportFromString(text), quest.id
        assert "focused reference" in text, quest.id
        generated += 1

    assert generated == 80


def test_no_room_requires_two_values_for_one_metadata_field() -> None:
    """One USDA field cannot simultaneously hold two scalar values."""
    for quest in QuestStore().all():
        seen: dict[tuple[str, str, str], object] = {}
        for rule in quest.validator.get("assertions", []):
            if "metadata_equals" not in rule:
                continue
            data = rule["metadata_equals"]
            target = (data.get("path", ""), data.get("key", ""), data.get("field", ""))
            value = data.get("value")
            assert target not in seen or seen[target] == value, (quest.id, target)
            seen[target] = value


def test_boss_debrief_is_free_and_points_to_usd_check(
    tmp_path: Path, monkeypatch
) -> None:
    client, _ = _client(
        tmp_path,
        monkeypatch,
        xp=1800,
        level=19,
        completed_quests=["f9_customizing_raid"],
    )
    failed = _run(client, "f9_hydra_brief", "this is not python(")
    assert failed["success"] is False
    before = client.get("/api/state").json()["opinion_points"]

    debrief = client.post("/api/quests/f9_hydra_brief/debrief").json()

    assert "USD Check" in debrief["message"]
    assert debrief["state"]["opinion_points"] == before


def test_internal_stage_observation_still_supports_contextual_hints(tmp_path: Path) -> None:
    stage = Usd.Stage.CreateNew(str(tmp_path / "relationship.usda"))
    bridge = stage.DefinePrim("/Bridge", "Xform")
    bridge.CreateRelationship("destination").SetTargets([Sdf.Path("/Depot")])

    reading = observe(stage, "relationship_targets", {"path": "/Bridge.destination"})

    assert reading == "It targets /Depot."
