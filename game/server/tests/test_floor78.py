from pathlib import Path

import pytest

from primventure.models import RunRequest
from primventure.runner import QuestRunner
from primventure.store import QuestStore, SaveStore


SOLUTIONS = {
    "f8_import_depot": """
imported.SetCustomDataByKey("sourceFormat", "OBJ")
imported.SetDocumentation("Normalized at intake.")
stage.GetRootLayer().Save()
""",
    "f8_extract_mesh": """
UsdGeom.Mesh.Define(stage, "/World/Cube").GetPointsAttr().Set(cube_points)
stage.GetRootLayer().Save()
""",
    "f8_extract_overseer": """
mesh.GetPointsAttr().Set([
    Gf.Vec3f(1, 1, 1), Gf.Vec3f(1, 1, -1), Gf.Vec3f(1, -1, 1), Gf.Vec3f(1, -1, -1),
    Gf.Vec3f(-1, 1, 1), Gf.Vec3f(-1, 1, -1), Gf.Vec3f(-1, -1, 1), Gf.Vec3f(-1, -1, -1),
])
stage.GetRootLayer().Save()
""",
    "f8_axis_switchyard": """
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
kiosk.AddTranslateOp().Set((10, 0, -4))
stage.GetRootLayer().Save()
""",
    "f8_unit_gauge": """
UsdGeom.SetStageMetersPerUnit(stage, UsdGeom.LinearUnits.centimeters)
stage.GetRootLayer().Save()
""",
    "f8_validate_warden": """
stage.SetDefaultPrim(world)
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
Usd.ModelAPI(world).SetKind(Kind.Tokens.component)
stage.GetRootLayer().Save()
""",
    "f8_customs_engine": """
stage.SetDefaultPrim(world)
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
UsdGeom.SetStageMetersPerUnit(stage, 0.01)
Usd.ModelAPI(world).SetKind(Kind.Tokens.component)
UsdGeom.Mesh.Define(stage, "/World/Cube").GetPointsAttr().Set(points[:8])
world.SetCustomDataByKey("sourceFormat", "OBJ")
stage.GetRootLayer().Save()
""",
    "f7_repeat_benches": """
for name in ("BenchA", "BenchB", "BenchC"):
    prim = stage.GetPrimAtPath(f"/City/InstanceWilds/{name}")
    prim.GetReferences().AddReference(bench)
    prim.SetInstanceable(True)
stage.GetRootLayer().Save()
""",
    "f7_prototype_sentinel": """
prim.SetDisplayName("Shared Foundry Bench")
stage.GetRootLayer().Save()
""",
    "f7_deinstance_sticker": """
unique = stage.GetPrimAtPath("/City/InstanceWilds/BenchC")
unique.SetInstanceable(False)
unique.SetDisplayName("Unique Sticker Bench")
stage.GetRootLayer().Save()
""",
    "f7_point_scatter": """
scatter.CreatePrototypesRel().SetTargets([proto.GetPath()])
scatter.CreateProtoIndicesAttr([0, 0, 0, 0])
scatter.CreatePositionsAttr([Gf.Vec3f(x, 0, 0) for x in (0, 2, 4, 6)])
stage.GetRootLayer().Save()
""",
    "f7_point_wastes_boss": """
scatter.CreatePrototypesRel().SetTargets([crate.GetPath(), seat.GetPath()])
scatter.CreateProtoIndicesAttr([0, 1, 0, 1])
scatter.CreatePositionsAttr([Gf.Vec3f(x, 0, 0) for x in (0, 2, 4, 6)])
stage.GetRootLayer().Save()
""",
    "f7_warehouse_district": """
for name in ("BenchA", "BenchB"):
    office = UsdGeom.Xform.Define(stage, f"/City/InstanceWilds/Warehouse/Office/{name}").GetPrim()
    office.GetReferences().AddReference(bench)
    office.SetInstanceable(True)
field = UsdGeom.PointInstancer.Define(stage, "/City/InstanceWilds/Warehouse/CrateField")
crate = stage.DefinePrim("/City/InstanceWilds/Warehouse/CrateField/Prototypes/Crate", "Xform")
crate.GetReferences().AddReference(cargo)
field.CreatePrototypesRel().SetTargets([crate.GetPath()])
field.CreateProtoIndicesAttr([0] * 6)
field.CreatePositionsAttr([Gf.Vec3f(i * 2.0, 0, 0) for i in range(6)])
stage.GetRootLayer().Save()
""",
    "f7_mirror_forge": """
prim.SetInstanceable(True)
stage.GetRootLayer().Save()
""",
}


@pytest.mark.parametrize("quest_id", SOLUTIONS)
def test_late_floor_starter_has_a_valid_completion(quest_id: str, tmp_path: Path) -> None:
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
