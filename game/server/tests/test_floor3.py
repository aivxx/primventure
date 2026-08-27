from pathlib import Path

import pytest

from primventure.models import RunRequest
from primventure.runner import QuestRunner
from primventure.store import QuestStore, SaveStore


SOLUTIONS = {
    "f3_layer_registry": """
stage.GetRootLayer().subLayerPaths = ["district_registry.usda"]
stage.GetRootLayer().Save()
""",
    "f3_layer_stack_boss": """
stage.GetRootLayer().subLayerPaths = ["commerce.usda", "safety.usda"]
stage.GetRootLayer().Save()
""",
    "f3_def_docket": """
stage.DefinePrim("/City/CompositionQuarter/CourtKiosk", "Cube")
stage.GetRootLayer().Save()
""",
    "f3_over_case": """
appeal.CreateAttribute("size", Sdf.ValueTypeNames.Double).Set(8.0)
stage.GetRootLayer().Save()
""",
    "f3_specifier_boss": """
booth = stage.DefinePrim("/City/CompositionQuarter/PermitBooth", "Xform")
booth.GetInherits().AddInherit(blueprint.GetPath())
stage.GetRootLayer().Save()
""",
    "f3_reference_license": """
destination.GetReferences().AddReference("arcade_sign.usda")
stage.GetRootLayer().Save()
""",
    "f3_default_gate": """
asset.SetDefaultPrim(kiosk)
asset.GetRootLayer().Save()
stage.Reload()
""",
    "f3_reference_arcade": """
sign.CreateAttribute("marquee", Sdf.ValueTypeNames.String).Set("THE CITY OWNS ITSELF")
stage.GetRootLayer().Save()
""",
    "f3_variant_switch": """
for name in ("day", "night"):
    modes.AddVariant(name)
    modes.SetVariantSelection(name)
    with modes.GetVariantEditContext():
        marquee.CreateAttribute("modeName", Sdf.ValueTypeNames.String).Set(name)
modes.SetVariantSelection("night")
stage.GetRootLayer().Save()
""",
    "f3_variant_boss": """
colors.SetVariantSelection("blue")
stage.GetRootLayer().Save()
""",
    "f3_city_block": """
for name in ("A", "B", "C"):
    child = stage.DefinePrim(f"/City/CompositionQuarter/ModularMarket/Stall_{name}", "Xform")
    child.GetReferences().AddReference("market_stall.usda")
    child.CreateAttribute("stallId", Sdf.ValueTypeNames.String).Set(name)
stage.GetRootLayer().Save()
""",
    "f3_opinion_colossus": """
boss.CreateAttribute("threatLevel", Sdf.ValueTypeNames.Int).Set(100)
stage.GetRootLayer().Save()
""",
}


@pytest.mark.parametrize("quest_id", SOLUTIONS)
def test_floor3_starter_has_a_valid_completion(quest_id: str, tmp_path: Path) -> None:
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

