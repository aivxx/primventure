from pathlib import Path

from fastapi.testclient import TestClient

from primventure.models import PlayerState
from primventure.runner import QuestRunner
from primventure.store import SaveStore, migrate
from primventure import runner as runner_module


EMPTY_STAGE = """
from pxr import Usd
stage = Usd.Stage.CreateNew(STAGE_PATH)
stage.GetRootLayer().Save()
"""

CITY_AS_XFORM = """
from pxr import Usd
stage = Usd.Stage.CreateNew(STAGE_PATH)
stage.DefinePrim("/City", "Xform")
stage.GetRootLayer().Save()
"""

CITY_AS_SCOPE = """
from pxr import Usd
stage = Usd.Stage.CreateNew(STAGE_PATH)
stage.DefinePrim("/City", "Scope")
stage.GetRootLayer().Save()
"""

MISSPELLED_CITY = """
from pxr import Usd
stage = Usd.Stage.CreateNew(STAGE_PATH)
stage.DefinePrim("/Citty", "Xform")
stage.GetRootLayer().Save()
"""

LOWERCASE_NAME = """
from pxr import Sdf, Usd
stage = Usd.Stage.CreateNew(STAGE_PATH)
city = stage.DefinePrim("/City", "Xform")
city.CreateAttribute("cityName", Sdf.ValueTypeNames.String).Set("primventure")
stage.GetRootLayer().Save()
"""

UNSET_NAME = """
from pxr import Sdf, Usd
stage = Usd.Stage.CreateNew(STAGE_PATH)
city = stage.DefinePrim("/City", "Xform")
city.CreateAttribute("cityName", Sdf.ValueTypeNames.String)
stage.GetRootLayer().Save()
"""


def _client(tmp_path: Path, monkeypatch, **state) -> TestClient:
    from primventure import api as api_module

    world = tmp_path / "world"
    world.mkdir()
    store = SaveStore(tmp_path / "save.json")
    monkeypatch.setattr(api_module, "WORLD_DIR", world)
    monkeypatch.setattr(runner_module, "WORLD_DIR", world)
    monkeypatch.setattr(api_module, "saves", store)
    monkeypatch.setattr(api_module, "runner", QuestRunner(store))
    defaults = dict(inventory={"hint_tokens": 0, "prim_censuses": 2})
    defaults.update(state)
    store.save(PlayerState(**defaults))
    return TestClient(api_module.app)


def _run(client: TestClient, quest: str, code: str) -> dict:
    return client.post(f"/api/quests/{quest}/run", json={"code": code, "language": "python"}).json()


def _stock(client: TestClient) -> int:
    return client.get("/api/state").json()["inventory"]["prim_censuses"]


def test_census_refuses_before_any_run(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    denied = client.post("/api/quests/f0_first_prim/census")
    assert denied.status_code == 409
    assert "Fail this room" in denied.json()["detail"]
    assert _stock(client) == 2


def test_census_refuses_a_clear(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    assert _run(client, "f0_first_prim", CITY_AS_XFORM)["success"] is True
    denied = client.post("/api/quests/f0_first_prim/census")
    assert denied.status_code == 409
    assert "Cleared rooms" in denied.json()["detail"]
    assert _stock(client) == 2


def test_census_refuses_a_failed_rerun_of_a_cleared_room(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    _run(client, "f0_first_prim", CITY_AS_XFORM)
    _run(client, "f0_first_prim", EMPTY_STAGE)
    denied = client.post("/api/quests/f0_first_prim/census")
    assert denied.status_code == 409
    assert _stock(client) == 2


def test_census_refuses_a_run_that_never_authored_a_stage(tmp_path: Path, monkeypatch) -> None:
    """Crashed code leaves only the seeded baseline, which is not the player's work."""
    client = _client(tmp_path, monkeypatch)
    failed = _run(client, "f0_first_prim", "this is not python(")
    assert failed["success"] is False
    denied = client.post("/api/quests/f0_first_prim/census")
    assert denied.status_code == 409
    assert "nothing to census" in denied.json()["detail"]
    assert _stock(client) == 2
    room = next(item for item in client.get("/api/quests").json() if item["id"] == "f0_first_prim")
    assert room["census_armed"] is False


def test_census_reports_a_stage_that_composed_nothing(tmp_path: Path, monkeypatch) -> None:
    """An empty stage is the reading a stuck beginner most needs."""
    client = _client(tmp_path, monkeypatch)
    assert _run(client, "f0_first_prim", EMPTY_STAGE)["success"] is False
    census = client.post("/api/quests/f0_first_prim/census").json()["census"]
    assert census["prims"] == []
    observed = " ".join(item["observed"] for item in census["observations"])
    assert "No prim at this path" in observed
    assert _stock(client) == 1


def test_census_reports_the_prims_the_stage_actually_composed(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    assert _run(client, "f0_first_prim", CITY_AS_SCOPE)["success"] is False
    room = next(item for item in client.get("/api/quests").json() if item["id"] == "f0_first_prim")
    assert room["census_armed"] is True
    assert room["census_paid"] is False

    census = client.post("/api/quests/f0_first_prim/census").json()["census"]

    city = next(prim for prim in census["prims"] if prim["path"] == "/City")
    assert city["type_name"] == "Scope"
    assert city["specifier"] == "def"
    # The failing check reports the real typeName, not the wanted one.
    observed = " ".join(item["observed"] for item in census["observations"])
    assert "Scope" in observed
    assert _stock(client) == 1


def test_census_points_at_a_near_miss_path(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    assert _run(client, "f0_first_prim", MISSPELLED_CITY)["success"] is False
    census = client.post("/api/quests/f0_first_prim/census").json()["census"]
    observed = " ".join(item["observed"] for item in census["observations"])
    assert "No prim at this path" in observed
    assert "/Citty" in observed


def test_census_reads_the_real_attribute_value_and_type(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch, completed_quests=["f0_first_prim"])
    assert _run(client, "f0_nameplate", LOWERCASE_NAME)["success"] is False
    census = client.post("/api/quests/f0_nameplate/census").json()["census"]
    observed = " ".join(item["observed"] for item in census["observations"])
    assert '"primventure"' in observed
    assert "string" in observed.lower()


def test_census_names_an_authored_attribute_holding_no_value(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch, completed_quests=["f0_first_prim"])
    assert _run(client, "f0_nameplate", UNSET_NAME)["success"] is False
    census = client.post("/api/quests/f0_nameplate/census").json()["census"]
    observed = " ".join(item["observed"] for item in census["observations"])
    assert "holds no value" in observed


def test_census_carries_stage_metadata(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    _run(client, "f0_first_prim", CITY_AS_SCOPE)
    stage = client.post("/api/quests/f0_first_prim/census").json()["census"]["stage"]
    assert stage["default_prim"] == ""
    assert stage["up_axis"]
    assert stage["sublayers"] == []


def test_a_paid_census_is_free_to_reread_until_the_next_run(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    _run(client, "f0_first_prim", CITY_AS_SCOPE)
    assert client.post("/api/quests/f0_first_prim/census").status_code == 200
    assert _stock(client) == 1

    again = client.post("/api/quests/f0_first_prim/census")
    assert again.status_code == 200
    assert _stock(client) == 1
    room = next(item for item in client.get("/api/quests").json() if item["id"] == "f0_first_prim")
    assert room["census_paid"] is True

    # A fresh fail is a fresh stage, so it charges again.
    _run(client, "f0_first_prim", EMPTY_STAGE)
    assert client.post("/api/quests/f0_first_prim/census").status_code == 200
    assert _stock(client) == 0


def test_census_refuses_at_zero_stock(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch, inventory={"hint_tokens": 0, "prim_censuses": 0})
    _run(client, "f0_first_prim", CITY_AS_SCOPE)
    denied = client.post("/api/quests/f0_first_prim/census")
    assert denied.status_code == 409
    assert "No Prim Censuses remain" in denied.json()["detail"]


def test_compositor_free_home_floor_census_after_a_fail(tmp_path: Path, monkeypatch) -> None:
    client = _client(
        tmp_path,
        monkeypatch,
        level=6,
        xp=520,
        specialization="Compositor",
        inventory={"hint_tokens": 0, "prim_censuses": 0},
        completed_quests=["f2_schema_warden"],
        benefit_claims={"starter_kit": True},
    )
    assert _run(client, "f3_layer_registry", EMPTY_STAGE)["success"] is False
    free = client.post("/api/quests/f3_layer_registry/census")
    assert free.status_code == 200
    assert free.json()["state"]["inventory"]["prim_censuses"] == 0

    # The perk is one per home floor, so a later fail on that floor pays cash.
    _run(client, "f3_layer_registry", CITY_AS_SCOPE)
    assert client.post("/api/quests/f3_layer_registry/census").status_code == 409


def test_curio_desk_restocks_censuses(tmp_path: Path, monkeypatch) -> None:
    client = _client(
        tmp_path,
        monkeypatch,
        level=3,
        xp=250,
        inventory={
            "hint_tokens": 0,
            "prim_censuses": 0,
            "Copper Scene Key": 1,
            "Archivist's Stylus": 1,
            "Threshold Transit Pass": 1,
            "Workstream Wedge": 1,
        },
    )
    body = client.post("/api/curio/prim_census").json()
    assert body["granted"] == {"prim_censuses": 2}
    assert body["state"]["inventory"]["prim_censuses"] == 2


def test_retired_consumables_migrate_into_censuses() -> None:
    raw = migrate(
        {
            "inventory": {"hint_tokens": 1, "system_peeks": 3, "inspectors_slips": 2},
            "benefit_claims": {"starter_kit": True, "free_peek:3": True},
            "upgrades": ["system_peek", "deeper_hints"],
            "last_fail": {"quest_id": "f0_first_prim", "results": [], "slip_index": 1},
        }
    )
    assert raw["inventory"]["prim_censuses"] == 5
    assert "system_peeks" not in raw["inventory"]
    assert "inspectors_slips" not in raw["inventory"]
    # The claimed free X-Ray stays claimed, so the rename grants no second use.
    assert raw["benefit_claims"]["free_census:3"] is True
    assert "free_peek:3" not in raw["benefit_claims"]
    assert raw["upgrades"] == ["prim_census", "deeper_hints"]
    assert "last_fail" not in raw


def test_migration_keeps_a_current_fail_readable() -> None:
    """Dropping this on every load would leave the census permanently unarmed."""
    fail = {"quest_id": "f0_first_prim", "has_stage": True, "prims": [], "paid": False}
    assert migrate({"last_fail": fail})["last_fail"] == fail


def test_a_migrated_save_loads(tmp_path: Path) -> None:
    path = tmp_path / "save.json"
    path.write_text(
        '{"version": 1, "inventory": {"hint_tokens": 1, "system_peeks": 4},'
        ' "benefit_claims": {"free_peek:5": true}}\n'
    )
    state = SaveStore(path).load()
    assert state.inventory["prim_censuses"] == 4
    assert state.benefit_claims == {"free_census:5": True}
    assert state.last_fail is None
