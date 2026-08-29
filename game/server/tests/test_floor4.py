from pathlib import Path

import pytest

from primventure.models import RunRequest
from primventure.runner import QuestRunner
from primventure.store import QuestStore, SaveStore


SOLUTIONS = {
    "f4_season_gate": """
primvar = UsdGeom.PrimvarsAPI(hedge.GetPrim()).CreatePrimvar(
    "displayColor", Sdf.ValueTypeNames.Color3fArray, UsdGeom.Tokens.constant
)
primvar.Set([Gf.Vec3f(0.0, 1.0, 0.0)])
stage.GetRootLayer().Save()
""",
    "f4_custom_tag": """
gate.CreateAttribute("primvars:notes:warden", Sdf.ValueTypeNames.String).Set("watch the north gate")
stage.GetRootLayer().Save()
""",
    "f4_two_faced_topiary": """
stage.GetPrimAtPath("/City/BeyondTheWalls/Topiary/Draft").SetActive(False)
stage.GetRootLayer().Save()
""",
    "f4_traversal_census": """
count = sum(1 for prim in stage.Traverse() if prim.GetTypeName() == "Mesh")
stage.GetPrimAtPath("/World").CreateAttribute("census", Sdf.ValueTypeNames.Int).Set(count)
stage.GetRootLayer().Save()
""",
    "f4_unit_contract": """
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
UsdGeom.SetStageMetersPerUnit(stage, 0.01)
stage.GetRootLayer().Save()
""",
    "f4_kind_post": """
Usd.ModelAPI(lamp).SetKind(Kind.Tokens.component)
stage.GetRootLayer().Save()
""",
    "f4_hydra_of_choices": """
stage.SetDefaultPrim(world)
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
UsdGeom.SetStageMetersPerUnit(stage, 0.01)
Usd.ModelAPI(world).SetKind(Kind.Tokens.component)
draft.GetPrim().SetActive(False)
UsdGeom.PrimvarsAPI(hero.GetPrim()).CreatePrimvar(
    "displayColor", Sdf.ValueTypeNames.Color3fArray, UsdGeom.Tokens.constant
).Set([Gf.Vec3f(1.0, 0.75, 0.25)])
stage.GetRootLayer().Save()
""",
}

MCQ = {
    "f4_two_faced_topiary": [0],
    "f4_kind_post": [0],
    "f4_hydra_lecture": [0],
    "f4_hydra_of_choices": [0],
}


@pytest.mark.parametrize("quest_id", SOLUTIONS)
def test_floor4_starter_has_a_valid_completion(quest_id: str, tmp_path: Path) -> None:
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
def test_floor4_mcq_answers(quest_id: str, tmp_path: Path) -> None:
    quest = QuestStore().get(quest_id)
    runner = QuestRunner(SaveStore(tmp_path / "save.json"))
    results = runner._validate_questions(quest, MCQ[quest_id])
    assert results and all(item.passed for item in results)
