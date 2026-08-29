from pathlib import Path

import pytest

from primventure.models import RunRequest
from primventure.runner import QuestRunner
from primventure.store import QuestStore, SaveStore


SOLUTIONS = {
    "f9_portfolio_gate": """
crown.GetPayloads().AddPayload(cargo)
crown.SetDocumentation("Portfolio capstone district.")
stage.GetRootLayer().Save()
""",
    "f9_edit_target_duel": """
world.SetDisplayName("Authored on notes")
stage.GetRootLayer().Save()
notes.Save()
""",
    "f9_stack_inspector": """
probe.CreateAttribute("signal", Sdf.ValueTypeNames.Int).Set(4)
stage.GetRootLayer().Save()
""",
    "f9_layer_offset_raid": """
dest.GetReferences().AddReference(Sdf.Reference("clip.usda", layerOffset=Sdf.LayerOffset(offset=10)))
stage.GetRootLayer().Save()
""",
    "f9_flatten_delivery": """
composed.Flatten().Export(STAGE_PATH)
""",
    "f9_changeblock_sprint": """
with Sdf.ChangeBlock():
    prim.CreateAttribute("a", Sdf.ValueTypeNames.Int).Set(1)
    prim.CreateAttribute("b", Sdf.ValueTypeNames.Int).Set(2)
    prim.CreateAttribute("c", Sdf.ValueTypeNames.Int).Set(3)
stage.GetRootLayer().Save()
""",
    "f9_archivist_prime": "",
    "f9_null_monarch": """
stage.SetDefaultPrim(city)
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
stage.SetStartTimeCode(1)
stage.SetEndTimeCode(48)
Usd.ModelAPI(city).SetKind(Kind.Tokens.group)
throne.GetReferences().AddReference(sign)
throne.SetInstanceable(True)
stage.GetRootLayer().Save()
""",
}

MCQ = {
    "f9_customizing_raid": [0, 0, 0, 0],
    "f9_hydra_brief": [0, 0],
    "f9_archivist_prime": [0, 0, 0, 0],
    "f9_null_monarch": [0],
}


@pytest.mark.parametrize("quest_id", list(SOLUTIONS))
def test_floor9_python_solutions(quest_id: str, tmp_path: Path) -> None:
    quest = QuestStore().get(quest_id)
    runner = QuestRunner(SaveStore(tmp_path / "save.json"))
    artifact, output, error = runner._execute(
        quest,
        RunRequest(code=quest.starter + "\n" + SOLUTIONS[quest_id]),
    )
    assert error is None, output
    results = runner._validate_stage(artifact, quest.validator["assertions"])
    failures = [result.message for result in results if not result.passed]
    assert not failures, failures


@pytest.mark.parametrize("quest_id", MCQ)
def test_floor9_mcq_answers(quest_id: str, tmp_path: Path) -> None:
    quest = QuestStore().get(quest_id)
    runner = QuestRunner(SaveStore(tmp_path / "save.json"))
    results = runner._validate_questions(quest, MCQ[quest_id])
    assert results and all(item.passed for item in results)
