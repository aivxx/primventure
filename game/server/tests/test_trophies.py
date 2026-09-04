from pathlib import Path

from fastapi.testclient import TestClient

from primventure.models import PlayerState
from primventure.store import SaveStore
from primventure.trophies import TROPHY_OP_COST, stamp, trophy_rows, unstamped


def _crawler(**kwargs) -> PlayerState:
    defaults = dict(
        level=3,
        xp=250,
        inventory={
            "hint_tokens": 0,
            "Copper Scene Key": 1,
            "Archivist's Stylus": 1,
            "Threshold Transit Pass": 1,
            "Workstream Wedge": 2,
        },
    )
    defaults.update(kwargs)
    return PlayerState(**defaults)


def test_consumables_are_not_trophies() -> None:
    names = [name for name, _, _ in trophy_rows(_crawler())]
    assert "hint_tokens" not in names
    assert unstamped(_crawler()) == 5


def test_stamping_walks_the_backpack_in_earn_order() -> None:
    state = _crawler()
    stamped = stamp(state, 3)
    assert stamped == {"Copper Scene Key": 1, "Archivist's Stylus": 1, "Threshold Transit Pass": 1}
    assert unstamped(state) == 2
    # The trophies themselves survive the trade, so the record still reads whole.
    assert state.inventory["Copper Scene Key"] == 1
    assert len(trophy_rows(state)) == 4


def test_stamping_spends_duplicate_units_one_at_a_time() -> None:
    state = _crawler(inventory={"Workstream Wedge": 3})
    assert stamp(state, 2) == {"Workstream Wedge": 2}
    assert unstamped(state) == 1
    assert stamp(state, 1) == {"Workstream Wedge": 1}
    assert unstamped(state) == 0
    assert stamp(state, 1) == {}


def test_cash_in_trades_trophies_for_one_opinion_point(tmp_path: Path, monkeypatch) -> None:
    from primventure import api as api_module

    monkeypatch.setattr(api_module, "saves", SaveStore(tmp_path / "save.json"))
    client = TestClient(api_module.app)
    api_module.saves.save(_crawler())
    traded = client.post("/api/trophies/cash-in")
    assert traded.status_code == 200
    body = traded.json()
    assert body["granted"] == {"opinion_points": 1}
    assert body["state"]["opinion_points"] == 1
    assert body["state"]["trophies"]["unstamped"] == 2
    assert body["state"]["trophies"]["op_cost"] == TROPHY_OP_COST
    assert body["state"]["inventory"]["hint_tokens"] == 0
    assert body["state"]["inventory"]["Copper Scene Key"] == 1


def test_cash_in_refuses_a_thin_backpack(tmp_path: Path, monkeypatch) -> None:
    from primventure import api as api_module

    monkeypatch.setattr(api_module, "saves", SaveStore(tmp_path / "save.json"))
    client = TestClient(api_module.app)
    api_module.saves.save(_crawler(inventory={"Copper Scene Key": 1}))
    denied = client.post("/api/trophies/cash-in")
    assert denied.status_code == 409
    assert "3 unstamped" in denied.json()["detail"]
    assert api_module.saves.load().stamped_items == {}
    assert api_module.saves.load().opinion_points == 0


def test_store_is_consumables_only(tmp_path: Path, monkeypatch) -> None:
    from primventure import api as api_module

    monkeypatch.setattr(api_module, "saves", SaveStore(tmp_path / "save.json"))
    client = TestClient(api_module.app)
    api_module.saves.save(_crawler(opinion_points=9, inventory={"Copper Scene Key": 9}))
    shop = client.get("/api/state").json()["shop"]
    assert list(shop) == ["hint_refill"]
    assert all(item["kind"] == "consumable" for item in shop.values())
    assert client.post("/api/shop/title_licensed").status_code == 404
    assert client.post("/api/shop/deeper_hints").status_code == 404
    assert "curio" not in client.get("/api/state").json()
