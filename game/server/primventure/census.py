"""Prim Census: what the failed stage actually held.

The room card already publishes the target state, so restating it teaches
nothing. Everything here reports the *composed* stage instead: the prims USD
resolved, their specifiers and types, and the real value behind each failing
check. That is the one view neither the checklist nor the USDA panel gives,
and reading it is the same skill the certification asks for.
"""
from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from pxr import Sdf, Usd, UsdGeom

from .expectations import payload_for
from .models import CensusNode, CheckObservation, LastFail, Quest, ValidationResult

# The census renders in a narrow rail, and a stage large enough to overflow it
# has already told the player what they needed from the first screenful.
MAX_PRIMS = 40
MAX_PROPERTIES = 8

SPECIFIERS = {
    Sdf.SpecifierDef: "def",
    Sdf.SpecifierOver: "over",
    Sdf.SpecifierClass: "class",
}
# Rules that describe the run itself rather than a prim on the stage.
RUN_RULES = frozenset({"execution", "stage_open", "orientation"})


def _rule_name(rule: dict[str, Any]) -> str:
    return str(rule.get("rule") or rule.get("type") or next(iter(rule), "unknown"))


def _plain(value: Any) -> Any:
    """Gf and Vt values do not serialize, and long arrays do not fit the rail."""
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if hasattr(value, "__len__") and not isinstance(value, (str, bytes)):
        try:
            items = list(value)
        except TypeError:
            return str(value)
        shown = [_plain(item) for item in items[:4]]
        return shown + [f"+{len(items) - 4} more"] if len(items) > 4 else shown
    return str(value)


def _show(value: Any) -> str:
    if value is None:
        return "nothing"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, list):
        return "[" + ", ".join(_show(item) for item in value) + "]"
    return str(value)


def _prim_path(path: Any) -> str:
    """Assertions address attributes as `/Prim.attribute`."""
    return str(path).split(".")[0] if path else ""


def nearest_paths(stage: Usd.Stage, target: str, limit: int = 2) -> list[str]:
    """Paths on the stage that look like a near miss for `target`."""
    if not target:
        return []
    existing = [prim.GetPath().pathString for prim in stage.TraverseAll()]
    if target in existing:
        return []
    lowered = {path.lower(): path for path in existing}
    if target.lower() in lowered:
        return [lowered[target.lower()]]
    return difflib.get_close_matches(target, existing, n=limit, cutoff=0.6)


def _missing(stage: Usd.Stage, prim_path: str) -> str:
    detail = "No prim at this path."
    nearest = nearest_paths(stage, prim_path)
    if nearest:
        detail += f" Nearest on your stage: {', '.join(nearest)}."
    return detail


def _attribute(stage: Usd.Stage, data: dict[str, Any], path: Any) -> Usd.Attribute | None:
    if path and "." in str(path):
        return stage.GetAttributeAtPath(str(path))
    prim = stage.GetPrimAtPath(str(path)) if path else None
    name = data.get("attribute")
    return prim.GetAttribute(name) if prim and prim.IsValid() and name else None


def _relationship(stage: Usd.Stage, data: dict[str, Any], path: Any) -> Usd.Relationship | None:
    if path and "." in str(path):
        return stage.GetRelationshipAtPath(str(path))
    prim = stage.GetPrimAtPath(str(path)) if path else None
    name = data.get("relationship")
    return prim.GetRelationship(name) if prim and prim.IsValid() and name else None


def _arc_assets(prim: Usd.Prim, field: str) -> list[str]:
    items = prim.GetMetadata(field)
    if not items:
        return []
    return [Path(item.assetPath).name or "<same layer>" for item in items.GetAppliedItems()]


def observe(stage: Usd.Stage, name: str, data: dict[str, Any]) -> str:
    """The real state behind one failing check, read off the composed stage."""
    path = data.get("path")
    prim_path = _prim_path(path)
    prim = stage.GetPrimAtPath(prim_path) if prim_path else None
    valid = bool(prim and prim.IsValid())

    if name in {"prim_exists", "prim_type", "kind_equals", "specifier_equals", "active", "instanceable"} and not valid:
        return _missing(stage, prim_path)

    if name == "prim_exists":
        return f'A prim exists here, typed "{prim.GetTypeName() or "(untyped)"}".'
    if name == "prim_type":
        return f'The prim exists but its typeName is "{prim.GetTypeName() or "(untyped)"}".'
    if name == "attribute_equals":
        attribute = _attribute(stage, data, path)
        if attribute is None or not attribute.IsValid():
            if not valid:
                return _missing(stage, prim_path)
            authored = list(prim.GetAuthoredPropertyNames())
            if authored:
                return (
                    "The prim exists but that property is not authored. "
                    f"Authored here: {', '.join(authored[:6])}."
                )
            return "The prim exists with no authored properties at all."
        value = attribute.Get(data["time"]) if "time" in data else attribute.Get()
        if value is None:
            return f"The attribute exists (type {attribute.GetTypeName()}) but holds no value."
        return f"It holds {_show(_plain(value))} (type {attribute.GetTypeName()})."
    if name == "relationship_targets":
        relationship = _relationship(stage, data, path)
        if relationship is None or not relationship.IsValid():
            if not valid:
                return _missing(stage, prim_path)
            authored = list(prim.GetAuthoredPropertyNames())
            if authored:
                return (
                    "The prim exists but that relationship is not authored. "
                    f"Authored here: {', '.join(authored[:6])}."
                )
            return "The prim exists with no authored properties at all."
        targets = [target.pathString for target in relationship.GetTargets()]
        if not targets:
            return "The relationship exists but targets nothing."
        return f"It targets {', '.join(targets)}."
    if name == "metadata_equals":
        key = data.get("metadata", data.get("key"))
        holder = prim if valid else stage
        value = holder.GetMetadata(key) if key else None
        field = data.get("field")
        if field and isinstance(value, dict):
            value = value.get(field)
        if value is None:
            return f"{key} is not authored here."
        return f"{key} holds {_show(_plain(value))}."
    if name == "kind_equals":
        kind = Usd.ModelAPI(prim).GetKind()
        return f'Its kind is "{kind}".' if kind else "The prim exists with no kind authored."
    if name in {"has_reference", "has_payload"}:
        field = "references" if name == "has_reference" else "payload"
        assets = _arc_assets(prim, field) if valid else []
        if not valid:
            return _missing(stage, prim_path)
        if not assets:
            return f"The prim exists with no authored {field}."
        return f"Authored {field}: {', '.join(assets)}."
    if name in {"has_inherit", "has_specializes"}:
        if not valid:
            return _missing(stage, prim_path)
        authored = prim.HasAuthoredInherits() if name == "has_inherit" else prim.HasAuthoredSpecializes()
        arc = "inherits" if name == "has_inherit" else "specializes"
        return f"The prim has an authored {arc} arc." if authored else f"The prim exists with no {arc} arc."
    if name == "has_variant_set":
        if not valid:
            return _missing(stage, prim_path)
        sets = list(prim.GetVariantSets().GetNames())
        if not sets:
            return "The prim exists with no variant sets."
        described = []
        for variant_set in sets:
            handle = prim.GetVariantSet(variant_set)
            selection = handle.GetVariantSelection() or "none"
            described.append(
                f"{variant_set} [{', '.join(handle.GetVariantNames())}] selected: {selection}"
            )
        return "Variant sets: " + "; ".join(described) + "."
    if name == "active":
        return f"The prim is {'active' if prim.IsActive() else 'deactivated'}."
    if name == "instanceable":
        return f"instanceable is {'true' if prim.IsInstanceable() else 'false'}."
    if name == "specifier_equals":
        return f'It is authored as "{SPECIFIERS.get(prim.GetSpecifier(), "unknown")}".'
    if name == "prim_stack":
        if not valid:
            return _missing(stage, prim_path)
        stack = list(prim.GetPrimStack())
        layers = [Path(spec.layer.identifier).name for spec in stack]
        return f"{len(stack)} spec(s) compose it, from: {', '.join(layers) or 'nothing'}."
    if name == "sublayer_order":
        actual = [Path(item).name for item in stage.GetRootLayer().subLayerPaths]
        if not actual:
            return "The root layer lists no sublayers."
        return f"Root sublayers, strongest first: {', '.join(actual)}."
    if name == "layer_offset":
        if not valid:
            return _missing(stage, prim_path)
        references = prim.GetMetadata("references")
        items = list(references.GetAppliedItems()) if references else []
        if not items:
            return "The prim exists with no authored references to carry an offset."
        pairs = [f"offset {item.layerOffset.offset}, scale {item.layerOffset.scale}" for item in items]
        return "Reference offsets: " + "; ".join(pairs) + "."
    if name == "attribute_source":
        attribute = stage.GetAttributeAtPath(str(path)) if path else None
        stack = attribute.GetPropertyStack() if attribute else []
        if not stack:
            return "No layer holds an opinion for that property."
        layers = [Path(spec.layer.identifier).name for spec in stack]
        return f"Opinions, strongest first: {', '.join(layers)}."
    if name == "traversal_contains":
        traversed = {str(item.GetPath()) for item in stage.Traverse()}
        wanted = [str(item) for item in data.get("paths", [])]
        missing = [item for item in wanted if item not in traversed]
        excluded = [item for item in data.get("excluded", []) if str(item) in traversed]
        parts = []
        if missing:
            parts.append(f"traversal never reached {', '.join(missing)}")
        if excluded:
            parts.append(f"it did reach {', '.join(str(item) for item in excluded)}")
        return ("Your " + " and ".join(parts) + ".") if parts else f"Traversal reached {len(traversed)} prim(s)."
    if name == "default_prim":
        default = stage.GetDefaultPrim()
        if not default or not default.IsValid():
            return "The stage has no default prim set."
        return f"The default prim is {default.GetPath().pathString}."
    if name == "up_axis":
        return f"The stage up axis is {UsdGeom.GetStageUpAxis(stage)}."
    if name == "meters_per_unit":
        return f"metersPerUnit is {UsdGeom.GetStageMetersPerUnit(stage)}."
    if name == "point_instancer":
        if not valid:
            return _missing(stage, prim_path)
        instancer = UsdGeom.PointInstancer(prim)
        indices = instancer.GetProtoIndicesAttr().Get() if instancer else None
        positions = instancer.GetPositionsAttr().Get() if instancer else None
        targets = list(instancer.GetPrototypesRel().GetTargets()) if instancer else []
        return (
            f"{len(indices or [])} protoIndices, {len(positions or [])} positions, "
            f"{len(targets)} prototype target(s)."
        )
    if name == "start_time":
        return f"The stage startTimeCode is {stage.GetStartTimeCode()}."
    if name == "end_time":
        return f"The stage endTimeCode is {stage.GetEndTimeCode()}."
    return f"The stage holds {len(list(stage.TraverseAll()))} prim(s)."


def stage_summary(stage: Usd.Stage) -> dict[str, Any]:
    default = stage.GetDefaultPrim()
    summary: dict[str, Any] = {
        "default_prim": default.GetPath().pathString if default and default.IsValid() else "",
        "up_axis": str(UsdGeom.GetStageUpAxis(stage) or ""),
        "meters_per_unit": UsdGeom.GetStageMetersPerUnit(stage),
        "sublayers": [Path(item).name for item in stage.GetRootLayer().subLayerPaths],
    }
    if stage.HasAuthoredTimeCodeRange():
        summary["time_range"] = [stage.GetStartTimeCode(), stage.GetEndTimeCode()]
    return summary


def stage_prims(stage: Usd.Stage) -> tuple[list[CensusNode], bool]:
    """Every prim USD resolved, inactive ones included, capped for display."""
    nodes: list[CensusNode] = []
    truncated = False
    for prim in stage.TraverseAll():
        if len(nodes) >= MAX_PRIMS:
            truncated = True
            break
        properties = list(prim.GetAuthoredPropertyNames())
        flags = []
        if not prim.IsActive():
            flags.append("inactive")
        if prim.IsInstanceable():
            flags.append("instanceable")
        if prim.HasAuthoredReferences():
            flags.append("references")
        if prim.HasAuthoredPayloads():
            flags.append("payload")
        if prim.HasAuthoredInherits():
            flags.append("inherits")
        if list(prim.GetVariantSets().GetNames()):
            flags.append("variants")
        nodes.append(
            CensusNode(
                path=prim.GetPath().pathString,
                specifier=SPECIFIERS.get(prim.GetSpecifier(), ""),
                type_name=str(prim.GetTypeName() or ""),
                kind=str(Usd.ModelAPI(prim).GetKind() or ""),
                properties=properties[:MAX_PROPERTIES],
                extra_properties=max(0, len(properties) - MAX_PROPERTIES),
                flags=flags,
            )
        )
    return nodes, truncated


def observations(
    quest: Quest, results: list[ValidationResult], stage: Usd.Stage | None
) -> list[CheckObservation]:
    """One reading per failing check, in the order the room declares them."""
    assertions = list(quest.validator.get("assertions", []))
    cursor = 0
    readings: list[CheckObservation] = []
    for result in results:
        if result.passed:
            continue
        if result.rule.startswith("question_"):
            readings.append(
                CheckObservation(
                    rule=result.rule,
                    target="Cookbook question",
                    observed="Your answer did not match the reading.",
                )
            )
            continue
        if result.rule in RUN_RULES:
            readings.append(
                CheckObservation(
                    rule=result.rule,
                    target="the submitted layer",
                    observed=result.message.strip()[:300] or "USD could not open a stage.",
                )
            )
            continue
        matched: dict[str, Any] | None = None
        for index in range(cursor, len(assertions)):
            if _rule_name(assertions[index]) == result.rule:
                matched = assertions[index]
                cursor = index + 1
                break
        data = payload_for(matched, result.rule) if matched else {}
        if stage is None:
            observed = result.message
        else:
            try:
                observed = observe(stage, result.rule, data)
            except Exception as exc:
                observed = f"The stage could not be read for this check: {exc}"
        readings.append(
            CheckObservation(
                rule=result.rule,
                target=str(data.get("path") or "the stage"),
                observed=observed,
            )
        )
    return readings


def snapshot(quest: Quest, artifact: Any, results: list[ValidationResult]) -> LastFail:
    """Record the failed stage now, while the submission still exists on disk."""
    # Code that crashed or would not parse never authored the stage on disk: the
    # runner seeds one, and censusing that would report the room's own baseline
    # back as the player's work. The traceback in the output is the real finding.
    crashed = any(
        not result.passed and result.rule in {"execution", "stage_open"} for result in results
    )
    stage = None
    if artifact is not None and not crashed:
        try:
            stage = Usd.Stage.Open(str(artifact))
        except Exception:
            stage = None
    prims, truncated = stage_prims(stage) if stage else ([], False)
    return LastFail(
        quest_id=quest.id,
        has_stage=stage is not None,
        stage=stage_summary(stage) if stage else {},
        prims=prims,
        truncated=truncated,
        observations=observations(quest, results, stage),
    )
