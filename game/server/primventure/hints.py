"""What a hint token buys: the call this room wants, or the check that missed.

Naming a rule and a cookbook path is not help a player can act on. A hint is
written as plain lines a stuck player can read top to bottom: what their stage
holds right now, what the check wants instead, the call that authors it, and
the page that teaches it. Before any run there is nothing composed to read, so
the hint opens on the first requirement instead.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .expectations import describe_assertion, payload_for
from .models import PlayerState, Quest


# The lesson that teaches each demand. Every path is asserted to exist, so a
# hint can never send a stuck player to a page that was renamed or removed.
DOC_PAGES: dict[str, str] = {
    "prim_exists": "docs/stage-setting/prims.md",
    "prim_type": "docs/stage-setting/prims.md",
    "attribute_equals": "docs/stage-setting/properties/attributes.md",
    "relationship_targets": "docs/stage-setting/properties/relationships.md",
    "metadata_equals": "docs/stage-setting/metadata.md",
    "kind_equals": "docs/beyond-basics/model-kinds.md",
    "active": "docs/beyond-basics/active-inactive-prims.md",
    "instanceable": (
        "docs/asset-modularity-instancing/authoring-scenegraph-instancing/"
        "scenegraph-instancing-intro.md"
    ),
    "specifier_equals": "docs/composition-basics/specifiers.md",
    "has_reference": "docs/creating-composition-arcs/references-payloads/working-with-references.md",
    "has_payload": "docs/creating-composition-arcs/references-payloads/working-with-payloads.md",
    "has_inherit": "docs/creating-composition-arcs/inherits-specializes/what-is-inherits.md",
    "has_specializes": "docs/creating-composition-arcs/inherits-specializes/what-is-specializes.md",
    "has_variant_set": "docs/composition-basics/variant-sets.md",
    "sublayer_order": "docs/creating-composition-arcs/sublayers/working-with-sublayers.md",
    "layer_offset": "docs/creating-composition-arcs/sublayers/working-with-sublayers.md",
    "prim_stack": "docs/creating-composition-arcs/prim-composition.md",
    "attribute_source": "docs/beyond-basics/value-resolution.md",
    "traversal_contains": "docs/beyond-basics/stage-traversal.md",
    "default_prim": "docs/composition-basics/default-prim.md",
    "up_axis": "docs/stage-setting/stage.md",
    "meters_per_unit": "docs/beyond-basics/units.md",
    "start_time": "docs/stage-setting/timecodes-timesamples.md",
    "end_time": "docs/stage-setting/timecodes-timesamples.md",
    "point_instancer": (
        "docs/asset-modularity-instancing/authoring-point-instancing/point-instancing-intro.md"
    ),
}


def _literal(value: Any) -> str:
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_literal(item) for item in value) + "]"
    return str(value)


def _prim(path: Any) -> str:
    return f'stage.GetPrimAtPath("{str(path).split(".")[0]}")'


def _value_type(value: Any) -> str:
    """Name the value type only where the expected value settles it."""
    if isinstance(value, bool):
        return "Sdf.ValueTypeNames.Bool"
    if isinstance(value, str):
        return "Sdf.ValueTypeNames.String"
    if isinstance(value, int):
        return "Sdf.ValueTypeNames.Int"
    # A float could be authored as Float or Double, and a sequence could be any
    # of the vector or array types, so the lesson has to settle those.
    return "Sdf.ValueTypeNames.<type>"


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _sentence(text: str) -> str:
    """Close a description, unless its own trailing quote already closes it."""
    return text if text.endswith((".", '"', "'")) else text + "."


def authoring_call(rule: dict[str, Any]) -> str:
    """The call that authors one demand, carrying this room's own path and value."""
    name = str(rule.get("rule") or rule.get("type") or next(iter(rule), "unknown"))
    data = payload_for(rule, name)
    path = data.get("path", "")
    expected = data.get("value", data.get("expected"))

    if name == "prim_exists":
        return f'stage.DefinePrim("{path}")'
    if name == "prim_type":
        return f'stage.DefinePrim("{path}", "{expected}")'
    if name == "attribute_equals":
        prim_path, _, attribute = str(path).partition(".")
        attribute = attribute or str(data.get("attribute", ""))
        at_time = f", Usd.TimeCode({data['time']})" if "time" in data else ""
        return (
            f'{_prim(prim_path)}.CreateAttribute("{attribute}", {_value_type(expected)})'
            f".Set({_literal(expected)}{at_time})"
        )
    if name == "relationship_targets":
        prim_path, _, relationship = str(path).partition(".")
        relationship = relationship or str(data.get("relationship", ""))
        targets = [str(target) for target in data.get("targets", expected or [])]
        return (
            f'{_prim(prim_path)}.CreateRelationship("{relationship}")'
            f".SetTargets({_literal(targets)})"
        )
    if name == "metadata_equals":
        key = data.get("metadata", data.get("key", "documentation"))
        if data.get("field"):
            return (
                f'{_prim(path)}.SetAssetInfoByKey("{data["field"]}", {_literal(expected)})'
                if key == "assetInfo"
                else f'{_prim(path)}.SetCustomDataByKey("{data["field"]}", {_literal(expected)})'
            )
        holder = _prim(path) if path else "stage"
        return f'{holder}.SetMetadata("{key}", {_literal(expected)})'
    if name == "kind_equals":
        return f"Usd.ModelAPI({_prim(path)}).SetKind({_literal(expected)})"
    if name == "active":
        return f"{_prim(path)}.SetActive({_literal(True if expected is None else expected)})"
    if name == "instanceable":
        return f"{_prim(path)}.SetInstanceable({_literal(True if expected is None else expected)})"
    if name == "specifier_equals":
        return (
            f'stage.CreateClassPrim("{path}")'
            if str(expected) == "class"
            else f'stage.OverridePrim("{path}")'
            if str(expected) == "over"
            else f'stage.DefinePrim("{path}")'
        )
    if name == "has_reference":
        return f'{_prim(path)}.GetReferences().AddReference("{data.get("asset", "<asset>")}")'
    if name == "has_payload":
        return f'{_prim(path)}.GetPayloads().AddPayload("{data.get("asset", "<asset>")}")'
    if name == "has_inherit":
        return f'{_prim(path)}.GetInherits().AddInherit("<class path>")'
    if name == "has_specializes":
        return f'{_prim(path)}.GetSpecializes().AddSpecialize("<fallback path>")'
    if name == "has_variant_set":
        variant_set = data.get("variant_set", data.get("name", "<set>"))
        return f'{_prim(path)}.GetVariantSets().AddVariantSet("{variant_set}")'
    if name == "sublayer_order":
        layers = [Path(str(layer)).name for layer in data.get("layers", [])]
        return f"stage.GetRootLayer().subLayerPaths = {_literal(layers)}"
    if name == "layer_offset":
        return "Sdf.Reference(assetPath, layerOffset=Sdf.LayerOffset(offset, scale))"
    if name == "prim_stack":
        return f"Author {path} in more than one layer, then read {_prim(path)}.GetPrimStack()"
    if name == "attribute_source":
        return f"Author a local opinion so {path} resolves from your own layer"
    if name == "traversal_contains":
        return "stage.Traverse() / stage.TraverseAll() after authoring or deactivating the prims"
    if name == "default_prim":
        return f'stage.SetDefaultPrim(stage.GetPrimAtPath("{expected or path}"))'
    if name == "up_axis":
        return f"UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.{str(expected).lower()})"
    if name == "meters_per_unit":
        return f"UsdGeom.SetStageMetersPerUnit(stage, {expected})"
    if name == "start_time":
        return f"stage.SetStartTimeCode({expected})"
    if name == "end_time":
        return f"stage.SetEndTimeCode({expected})"
    if name == "point_instancer":
        return f'UsdGeom.PointInstancer.Define(stage, "{path}")'
    return f"Author {path or 'the stage'} so the {name.replace('_', ' ')} check passes"


def _reading(quest: Quest, state: PlayerState, index: int) -> str:
    """What the submitted stage actually held for the check that missed."""
    fail = state.last_fail
    if fail is None:
        return ""
    wanted = describe_assertion(quest.validator["assertions"][index])
    for observation, description in zip(fail.observations, fail.failed_checks):
        if description == wanted:
            return observation.observed
    return ""


def hint_for(quest: Quest, state: PlayerState) -> str:
    rules = quest.validator.get("assertions", [])
    fail = state.last_fail
    missed = (
        list(fail.failed_assertions)
        if fail is not None and fail.quest_id == quest.id and quest.id not in state.completed_quests
        else []
    )

    if not rules:
        if quest.questions:
            return (
                f"This room grades the briefing question, not a stage. Re-read {quest.cookbook} "
                "and answer from the lesson rather than the room title."
            )
        return f"Nothing here is validated against a stage. Read {quest.cookbook}."

    if missed:
        index = missed[0]
        rule = rules[index]
        name = str(rule.get("rule") or rule.get("type") or next(iter(rule), "unknown"))
        others = len(missed) - 1
        lines = [f"Check {index + 1} of {len(rules)} missed."]
        reading = _reading(quest, state, index)
        if reading:
            lines.append(f"Your stage right now: {reading}")
        lines += [
            f"It passes when: {_sentence(describe_assertion(rule))}",
            f"Write it like this: {authoring_call(rule)}",
        ]
        if others:
            lines.append(f"{_plural(others, 'other check')} also missed.")
        lines.append(f"Lesson: {DOC_PAGES.get(name, quest.cookbook)}.")
        return "\n".join(lines)

    if fail is not None and fail.quest_id == quest.id and not missed:
        return (
            "Your last run stopped before any check could read the stage.\n"
            "Fix the error printed in the run output first.\n"
            f"Lesson: {quest.cookbook}."
        )

    rule = rules[0]
    name = str(rule.get("rule") or rule.get("type") or next(iter(rule), "unknown"))
    others = len(rules) - 1
    lines = [
        f"Nothing has run yet, so start with check 1 of {len(rules)}.",
        f"It passes when: {_sentence(describe_assertion(rule))}",
        f"Write it like this: {authoring_call(rule)}",
        f"Run the room to see which of the {_plural(others, 'other check')} still miss."
        if others
        else "That is the only check this room grades.",
        f"Lesson: {DOC_PAGES.get(name, quest.cookbook)}.",
    ]
    return "\n".join(lines)
