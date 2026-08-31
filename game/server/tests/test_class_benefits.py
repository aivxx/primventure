from pathlib import Path

from fastapi.testclient import TestClient

from primventure.benefits import (
    home_boss_bonus,
    is_home_floor,
    preview_boss_fee,
    recipe_bonus,
)
from primventure.models import PlayerState, Quest
from primventure.runner import QuestRunner
from primventure.store import SaveStore, opinion_points_for, quest_view


def _boss(**kwargs) -> Quest:
    defaults = dict(
        id="boss",
        title="Boss",
        floor=3,
        neighborhood="Lane",
        kind="floor_boss",
        brief="Fight.",
        cookbook="docs/index.md",
        language="none",
    )
    defaults.update(kwargs)
    return Quest(**defaults)


def test_home_floors_follow_ui_numbering_not_filename_prefixes() -> None:
    assert is_home_floor("Aggregator", 8)
    assert not is_home_floor("Aggregator", 7)
    assert is_home_floor("Exchanger", 7)
    assert not is_home_floor("Exchanger", 8)
    assert is_home_floor("Compositor", 3)
    assert is_home_floor("Compositor", 5)


def test_tiered_home_boss_bonus_balances_short_exchanger_track() -> None:
    assert home_boss_bonus("Compositor", _boss(kind="neighborhood_boss", floor=3)) == 0
    assert home_boss_bonus("Compositor", _boss(kind="city_boss", floor=3)) == 1
    assert home_boss_bonus("Compositor", _boss(kind="floor_boss", floor=3)) == 2
    assert home_boss_bonus("Exchanger", _boss(kind="neighborhood_boss", floor=7)) == 1
    assert home_boss_bonus("Exchanger", _boss(kind="city_boss", floor=7)) == 2
    assert home_boss_bonus("Exchanger", _boss(kind="floor_boss", floor=3)) == 0


def test_quest_view_advertises_class_bonus(tmp_path: Path) -> None:
    quest = _boss(kind="floor_boss", floor=5, reward={"opinion_points": 3})
    state = PlayerState(specialization="Compositor")
    assert quest_view(quest, state)["opinion_points"] == 5
    assert opinion_points_for(quest) == 3


def test_recipe_drip_caps_at_five() -> None:
    state = PlayerState(specialization="Compositor", recipe_drip_op=4)
    gained = recipe_bonus(state, ["Layer", "Sublayer", "Opinions"])
    assert gained == 1


def test_specialization_grants_kit_once(tmp_path: Path, monkeypatch) -> None:
    from primventure import api as api_module

    monkeypatch.setattr(api_module, "saves", SaveStore(tmp_path / "save.json"))
    client = TestClient(api_module.app)
    api_module.saves.save(PlayerState(level=2, xp=120))
    first = client.post("/api/specialization/Compositor").json()
    assert first["specialization"] == "Compositor"
    assert first["inventory"]["prim_censuses"] == 2
    assert first["title"].startswith("Compositor")
    again = client.post("/api/specialization/Compositor").json()
    assert again["inventory"]["prim_censuses"] == 2
    denied = client.post("/api/specialization/Aggregator")
    assert denied.status_code == 409


def test_aggregator_hint_restock_grants_three(tmp_path: Path, monkeypatch) -> None:
    from primventure import api as api_module

    monkeypatch.setattr(api_module, "saves", SaveStore(tmp_path / "save.json"))
    client = TestClient(api_module.app)
    api_module.saves.save(PlayerState(
        level=2, xp=120, opinion_points=4, specialization="Aggregator",
        benefit_claims={"starter_kit": True},
    ))
    bought = client.post("/api/shop/hint_refill").json()
    assert bought["inventory"]["hint_tokens"] == 5
    assert bought["shop"]["hint_refill"]["inventory"]["hint_tokens"] == 3


def test_compositor_census_costs_one(tmp_path: Path, monkeypatch) -> None:
    from primventure import api as api_module

    monkeypatch.setattr(api_module, "saves", SaveStore(tmp_path / "save.json"))
    client = TestClient(api_module.app)
    api_module.saves.save(PlayerState(
        level=2, xp=120, opinion_points=1, specialization="Compositor",
        benefit_claims={"starter_kit": True},
    ))
    bought = client.post("/api/shop/prim_census").json()
    assert bought["opinion_points"] == 0
    assert bought["inventory"]["prim_censuses"] == 3


def test_free_hint_on_home_floor_at_zero_stock(tmp_path: Path, monkeypatch) -> None:
    from primventure import api as api_module

    monkeypatch.setattr(api_module, "saves", SaveStore(tmp_path / "save.json"))
    client = TestClient(api_module.app)
    api_module.saves.save(PlayerState(
        level=6, xp=520, specialization="Aggregator",
        inventory={"hint_tokens": 0, "prim_censuses": 0},
        benefit_claims={"starter_kit": True},
    ))
    first = client.post("/api/quests/f6_entry_point/hint")
    assert first.status_code == 200
    assert first.json()["state"]["inventory"]["hint_tokens"] == 0
    second = client.post("/api/quests/f6_hierarchy_sort/hint")
    assert second.status_code == 409


def test_home_boss_fee_is_halved() -> None:
    state = PlayerState(xp=150, level=2, specialization="Compositor")
    fee, kind = preview_boss_fee(state, _boss(floor=3))
    assert kind == "home"
    assert fee == 12


def test_exchanger_waiver_then_half(tmp_path: Path) -> None:
    from primventure.models import Question, RunRequest

    quest = _boss(
        id="customs-boss",
        floor=7,
        kind="city_boss",
        questions=[Question(prompt="Nope", choices=["a", "b"], answer=1)],
    )
    saves = SaveStore(tmp_path / "save.json")
    saves.save(PlayerState(xp=150, level=2, specialization="Exchanger", benefit_claims={"starter_kit": True}))
    runner = QuestRunner(saves)
    first = runner.run(quest, RunRequest(answers=[0]))
    assert first.success is False
    assert "waived" in first.system_message.lower()
    assert saves.load().xp == 150
    second = runner.run(quest, RunRequest(answers=[0]))
    assert "Boss fee: 12 XP" in second.system_message
    assert saves.load().xp == 138
