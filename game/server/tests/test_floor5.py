from pathlib import Path

import pytest

from primventure.models import RunRequest
from primventure.runner import QuestRunner
from primventure.store import QuestStore, SaveStore


SOLUTIONS = {
    "f5_sublayer_workstreams": """
stage.GetRootLayer().subLayerPaths = ["shading.usda", "geometry.usda"]
stage.GetRootLayer().Save()
""",
    "f5_workstream_clerk": """
stage.GetRootLayer().subLayerPaths = ["lighting.usda", "layout.usda"]
stage.GetRootLayer().Save()
""",
    "f5_skyline_references": """
for path, asset in (
    ("/World/skyscraperA_01", a),
    ("/World/skyscraperA_02", a),
    ("/World/skyscraperE_01", e),
):
    UsdGeom.Xform.Define(stage, path).GetPrim().GetReferences().AddReference(asset)
stage.GetRootLayer().Save()
""",
    "f5_encapsulation_raid": """
stage.SetDefaultPrim(world.GetPrim())
stage.DefinePrim("/World/Looks", "Scope")
UsdShade.Material.Define(stage, "/World/Looks/Red")
stage.GetRootLayer().Save()
""",
    "f5_sealed_crate": """
for name in ("sm_bldgF_01", "sm_bldgF_02", "sm_bldgF_03"):
    UsdGeom.Xform.Define(stage, f"/World/{name}").GetPrim().GetPayloads().AddPayload(building)
stage.GetRootLayer().Save()
""",
    "f5_harbor_master": """
crate.SetDocumentation("Loaded on demand.")
stage.GetRootLayer().Save()
""",
    "f5_inherit_lamps": """
klass = stage.CreateClassPrim("/_street_lamp_dbl")
klass.CreateAttribute("temperature", Sdf.ValueTypeNames.Int).Set(2700)
lamp.GetInherits().AddInherit(klass.GetPath())
stage.GetRootLayer().Save()
""",
    "f5_specializes_fallback": """
road.GetSpecializes().AddSpecialize(fallback.GetPath())
road.CreateAttribute("osm:street:maxspeed", Sdf.ValueTypeNames.Int).Set(20)
stage.GetRootLayer().Save()
""",
    "f5_city_block": """
for path, asset, payload in (
    ("/City/ArcHighlands/HighlandBlock/TowerA", tower_a, False),
    ("/City/ArcHighlands/HighlandBlock/TowerE", tower_e, False),
    ("/City/ArcHighlands/HighlandBlock/Warehouse", warehouse, True),
):
    prim = UsdGeom.Xform.Define(stage, path).GetPrim()
    if payload:
        prim.GetPayloads().AddPayload(asset)
    else:
        prim.GetReferences().AddReference(asset)
stage.GetRootLayer().Save()
""",
    "f5_liverps_labyrinth": """
sign.CreateAttribute("floorIndex", Sdf.ValueTypeNames.Int).Set(4)
stage.GetRootLayer().Save()
""",
}


@pytest.mark.parametrize("quest_id", SOLUTIONS)
def test_floor5_starter_has_a_valid_completion(quest_id: str, tmp_path: Path) -> None:
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
