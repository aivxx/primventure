from pathlib import Path

import pytest

from primventure.models import RunRequest
from primventure.runner import QuestRunner
from primventure.store import QuestStore, SaveStore


SOLUTIONS = {
    "f6_entry_point": """
world = UsdGeom.Xform.Define(stage, "/World").GetPrim()
stage.SetDefaultPrim(world)
editor = Usd.NamespaceEditor(stage)
editor.ReparentPrim(stage.GetPrimAtPath("/Hull"), world)
editor.ApplyEdits()
stage.GetRootLayer().Save()
""",
    "f6_hierarchy_sort": """
stage.DefinePrim("/World/Looks", "Scope")
UsdShade.Material.Define(stage, "/World/Looks/Paint")
stage.GetRootLayer().Save()
""",
    "f6_workstream_split": """
stage.GetRootLayer().subLayerPaths = ["shading.usda", "geometry.usda"]
stage.GetRootLayer().Save()
""",
    "f6_asset_interface": """
stage.SetDefaultPrim(world.GetPrim())
world.GetPrim().GetPayloads().AddPayload("contents.usda")
stage.GetRootLayer().Save()
""",
    "f6_accent_parameter": """
UsdGeom.PrimvarsAPI(world.GetPrim()).CreatePrimvar(
    "accentColor", Sdf.ValueTypeNames.Float3, UsdGeom.Tokens.constant
).Set((1.0, 0.0, 0.0))
stage.GetRootLayer().Save()
""",
    "f6_loft_variant": """
lofted = world.GetVariantSets().AddVariantSet("paint")
for name in ("brick", "stucco"):
    lofted.AddVariant(name)
lofted.SetVariantSelection("brick")
stage.GetRootLayer().Save()
""",
    "f6_component_house": """
Usd.ModelAPI(house).SetKind(Kind.Tokens.component)
Usd.ModelAPI(house).SetAssetName("Townhouse")
stage.GetRootLayer().Save()
""",
    "f6_assembly_block": """
Usd.ModelAPI(block).SetKind(Kind.Tokens.assembly)
UsdGeom.Xform.Define(stage, "/City/AssetFoundry/SkylineBlock/SignA").GetPrim().GetReferences().AddReference(sign)
stage.GetRootLayer().Save()
""",
    "f6_street_groups": """
for name in ("North", "South"):
    child = UsdGeom.Xform.Define(stage, f"/World/{name}")
    Usd.ModelAPI(child).SetKind(Kind.Tokens.group)
stage.GetRootLayer().Save()
""",
    "f6_zoning_golem": """
Usd.ModelAPI(district).SetKind(Kind.Tokens.group)
Usd.ModelAPI(block).SetKind(Kind.Tokens.assembly)
Usd.ModelAPI(house).SetKind(Kind.Tokens.component)
stage.GetRootLayer().Save()
""",
}


@pytest.mark.parametrize("quest_id", SOLUTIONS)
def test_floor6_starter_has_a_valid_completion(quest_id: str, tmp_path: Path) -> None:
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
