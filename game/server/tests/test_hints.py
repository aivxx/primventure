from pathlib import Path

from fastapi.testclient import TestClient

from primventure.hints import DOC_PAGES, authoring_call, hint_for
from primventure.models import PlayerState, RunRequest
from primventure.runner import QuestRunner
from primventure import runner as runner_module
from primventure.store import ROOT, QuestStore, SaveStore

COMMENT_INSTEAD_OF_DOCUMENTATION = """
globe = stage.DefinePrim("/City/PropertyWard/LampGlobe", "Sphere")
globe.SetMetadata("comment", "Glass blown on floor one.")
stage.GetRootLayer().Save()
"""


def _missed_record(tmp_path: Path, monkeypatch) -> tuple[SaveStore, object]:
    """Fail the metadata room the way stamping `comment` alone fails it."""
    world = tmp_path / "world"
    world.mkdir()
    monkeypatch.setattr(runner_module, "WORLD_DIR", world)
    quest = QuestStore().get("f1_records_office")
    saves = SaveStore(tmp_path / "save.json")
    saves.save(PlayerState(xp=500, level=6, completed_quests=["f1_module_desk"]))
    missed = QuestRunner(saves).run(
        quest, RunRequest(code=quest.starter + "\n" + COMMENT_INSTEAD_OF_DOCUMENTATION)
    )
    assert not missed.success
    return saves, quest


def test_a_hint_before_any_run_fills_in_the_call_for_the_first_check() -> None:
    quest = QuestStore().get("f2_relationship_bridge")

    hint = hint_for(quest, PlayerState())

    assert "check 1 of 3" in hint
    assert 'stage.DefinePrim("/City/PropertyWard/Bridge", "Xform")' in hint
    assert "docs/stage-setting/prims.md" in hint
    # The other two demands stay for the player to author.
    assert "SetTargets" not in hint


def test_a_hint_after_a_miss_names_the_check_that_failed_and_its_call(
    tmp_path: Path, monkeypatch
) -> None:
    """The generic rule list never told a player which demand they had missed."""
    saves, quest = _missed_record(tmp_path, monkeypatch)

    hint = hint_for(quest, saves.load())

    assert "Check 1 of 2 missed" in hint
    assert 'SetMetadata("documentation"' in hint
    assert "docs/stage-setting/metadata.md" in hint
    # The passing checks are not restated.
    assert "DefinePrim" not in hint


def test_a_hint_contrasts_what_the_stage_holds_with_what_the_check_wants(
    tmp_path: Path, monkeypatch
) -> None:
    """A rule name alone never told a player how their own stage differed."""
    saves, quest = _missed_record(tmp_path, monkeypatch)

    hint = hint_for(quest, saves.load())

    assert "Your stage right now: documentation is not authored here." in hint
    assert "It passes when: /City/PropertyWard/LampGlobe carries documentation" in hint
    assert "Write it like this: " in hint


def test_a_hint_after_a_crash_sends_the_player_to_the_run_output(
    tmp_path: Path, monkeypatch
) -> None:
    """No check ever read the stage, so naming one would be a guess."""
    world = tmp_path / "world"
    world.mkdir()
    monkeypatch.setattr(runner_module, "WORLD_DIR", world)
    quest = QuestStore().get("f0_first_prim")
    saves = SaveStore(tmp_path / "save.json")
    saves.save(PlayerState(completed_quests=["f0_stage_intake"]))
    QuestRunner(saves).run(quest, RunRequest(code="this is not python("))

    hint = hint_for(quest, saves.load())

    assert "stopped before any check could read the stage" in hint
    assert quest.cookbook in hint


def test_a_hint_for_a_briefing_room_does_not_invent_a_call() -> None:
    quest = QuestStore().get("f9_hydra_brief")
    briefing = quest.model_copy(update={"validator": {"assertions": []}})

    hint = hint_for(briefing, PlayerState())

    assert "briefing question" in hint
    assert quest.cookbook in hint


def test_every_room_hint_names_a_call_and_a_page_that_exists() -> None:
    """A hint costs a token, so it may never answer with a rule name alone."""
    for quest in QuestStore().all():
        hint = hint_for(quest, PlayerState())

        assert hint.strip().endswith("."), quest.id
        assert "unknown" not in hint, quest.id
        for rule in quest.validator.get("assertions", []):
            name = str(rule.get("rule") or rule.get("type") or next(iter(rule)))
            assert not authoring_call(rule).startswith("Author the stage"), (quest.id, name)


def test_every_mapped_lesson_page_is_on_disk() -> None:
    """A hint that points at a renamed page is worse than no hint."""
    for rule, page in DOC_PAGES.items():
        assert (ROOT / page).is_file(), (rule, page)


def test_the_hint_endpoint_still_charges_exactly_one_token(
    tmp_path: Path, monkeypatch
) -> None:
    from primventure import api as api_module

    store = SaveStore(tmp_path / "save.json")
    monkeypatch.setattr(api_module, "saves", store)
    monkeypatch.setattr(api_module, "runner", QuestRunner(store))
    store.save(PlayerState(inventory={"hint_tokens": 1}))
    client = TestClient(api_module.app)

    bought = client.post("/api/quests/f0_first_prim/hint")
    assert bought.status_code == 200
    assert bought.json()["state"]["inventory"]["hint_tokens"] == 0
    assert 'stage.DefinePrim("/City"' in bought.json()["hint"]

    assert client.post("/api/quests/f0_first_prim/hint").status_code == 409
