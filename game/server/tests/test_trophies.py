from pathlib import Path

from fastapi.testclient import TestClient

from primventure.models import PlayerState
from primventure.store import SaveStore
from primventure.trophies import stamp, trophy_rows, unstamped


def _crawler(**kwargs) -> PlayerState:
    defaults = dict(
        level=3,
        xp=250,
        inventory={
            "hint_tokens": 0,
            "prim_censuses": 0,
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
    assert "prim_censuses" not in names
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


def test_desk_trades_trophies_for_hints(tmp_path: Path, monkeypatch) -> None:
    from primventure import api as api_module

    monkeypatch.setattr(api_module, "saves", SaveStore(tmp_path / "save.json"))
    client = TestClient(api_module.app)
    api_module.saves.save(_crawler())
    traded = client.post("/api/curio/hint_refill")
    assert traded.status_code == 200
    body = traded.json()
    assert body["granted"] == {"hint_tokens": 2}
    assert body["state"]["inventory"]["hint_tokens"] == 2
    assert body["state"]["curio"]["unstamped"] == 2
    # Trading is not a purchase, so the boss-only currency is untouched.
    assert body["state"]["opinion_points"] == 0


def test_desk_refuses_a_thin_backpack(tmp_path: Path, monkeypatch) -> None:
    from primventure import api as api_module

    monkeypatch.setattr(api_module, "saves", SaveStore(tmp_path / "save.json"))
    client = TestClient(api_module.app)
    api_module.saves.save(_crawler(inventory={"Copper Scene Key": 1}))
    denied = client.post("/api/curio/prim_census")
    assert denied.status_code == 409
    assert "4 unstamped" in denied.json()["detail"]
    assert api_module.saves.load().stamped_items == {}


def test_desk_only_appraises_consumable_offers(tmp_path: Path, monkeypatch) -> None:
    from primventure import api as api_module

    monkeypatch.setattr(api_module, "saves", SaveStore(tmp_path / "save.json"))
    client = TestClient(api_module.app)
    api_module.saves.save(_crawler(inventory={"Copper Scene Key": 9}))
    assert client.post("/api/curio/title_licensed").status_code == 404
    assert client.post("/api/curio/deeper_hints").status_code == 404


def test_class_bulk_rate_carries_into_trophy_trades(tmp_path: Path, monkeypatch) -> None:
    from primventure import api as api_module

    monkeypatch.setattr(api_module, "saves", SaveStore(tmp_path / "save.json"))
    client = TestClient(api_module.app)
    api_module.saves.save(_crawler(
        specialization="Aggregator",
        benefit_claims={"starter_kit": True},
    ))
    body = client.post("/api/curio/hint_refill").json()
    assert body["granted"] == {"hint_tokens": 3}
    assert body["state"]["inventory"]["hint_tokens"] == 3
