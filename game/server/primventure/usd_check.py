"""Build a compact USDA reference from a room's graded assertions.

This is intentionally not a canonical full solution. USD often has several
valid authoring paths, and some checks concern composition across files. A USD
Check shows the opinions the validator wants to see in the resulting layer,
plus comments for checks that cannot be represented by one local USDA file.
"""

from __future__ import annotations

from typing import Any

from pxr import Gf, Kind, Sdf, Usd, UsdGeom, Vt

from .expectations import payload_for
from .models import Quest


def _rule_name(rule: dict[str, Any]) -> str:
    return str(rule.get("rule") or rule.get("type") or next(iter(rule), "unknown"))


def _property_path(path: Any, data: dict[str, Any], key: str) -> tuple[str, str]:
    prim_path, dot, name = str(path or "").partition(".")
    return prim_path, name if dot else str(data.get(key, ""))


def _ensure_prim(stage: Usd.Stage, path: Any, type_name: str = "") -> Usd.Prim:
    prim = stage.GetPrimAtPath(str(path))
    if prim and prim.IsValid():
        if type_name:
            prim.SetTypeName(type_name)
        return prim
    return stage.DefinePrim(str(path), type_name)


def _attribute_type(path: str, value: Any) -> Sdf.ValueTypeName:
    name = path.rsplit(".", 1)[-1]
    if name == "points":
        return Sdf.ValueTypeNames.Point3fArray
    if name == "primvars:displayColor":
        return Sdf.ValueTypeNames.Color3fArray
    if name == "primvars:accentColor":
        return Sdf.ValueTypeNames.Color3f
    if name == "xformOp:translate":
        return Sdf.ValueTypeNames.Double3
    if isinstance(value, bool):
        return Sdf.ValueTypeNames.Bool
    if isinstance(value, int):
        return Sdf.ValueTypeNames.Int
    if isinstance(value, float):
        return Sdf.ValueTypeNames.Double
    if isinstance(value, str):
        return Sdf.ValueTypeNames.String
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return Sdf.ValueTypeNames.StringArray
    if isinstance(value, list) and len(value) == 3:
        return Sdf.ValueTypeNames.Double3
    return Sdf.ValueTypeNames.String


def _attribute_value(type_name: Sdf.ValueTypeName, value: Any) -> Any:
    if type_name == Sdf.ValueTypeNames.Double3:
        return Gf.Vec3d(*value)
    if type_name == Sdf.ValueTypeNames.Color3f:
        return Gf.Vec3f(*value)
    if type_name in {Sdf.ValueTypeNames.Point3fArray, Sdf.ValueTypeNames.Color3fArray}:
        return Vt.Vec3fArray([Gf.Vec3f(*item) for item in value])
    if type_name == Sdf.ValueTypeNames.StringArray:
        return Vt.StringArray(value)
    return value


def _author_attribute(stage: Usd.Stage, path: Any, data: dict[str, Any]) -> None:
    prim_path, name = _property_path(path, data, "attribute")
    prim = _ensure_prim(stage, prim_path)
    value = data.get("value", data.get("expected"))
    attribute = prim.GetAttribute(name)
    if not attribute or not attribute.IsValid():
        value_type = _attribute_type(str(path), value)
        attribute = prim.CreateAttribute(name, value_type, custom=True)
    else:
        value_type = attribute.GetTypeName()
    authored = _attribute_value(value_type, value)
    if "time" in data:
        attribute.Set(authored, Usd.TimeCode(data["time"]))
    else:
        attribute.Set(authored)


def _author_metadata(stage: Usd.Stage, data: dict[str, Any]) -> None:
    prim = _ensure_prim(stage, data.get("path"))
    key = data.get("metadata", data.get("key"))
    value = data.get("value", data.get("expected"))
    field = data.get("field")
    if field and key == "assetInfo":
        prim.SetAssetInfoByKey(field, value)
    elif field and key == "customData":
        prim.SetCustomDataByKey(field, value)
    elif key == "kind":
        Usd.ModelAPI(prim).SetKind(value)
    elif key == "documentation":
        prim.SetDocumentation(value)
    elif key == "displayName":
        prim.SetDisplayName(value)
    else:
        prim.SetMetadata(key, value)


def _author_point_instancer(stage: Usd.Stage, data: dict[str, Any]) -> None:
    instancer = UsdGeom.PointInstancer.Define(stage, data["path"])
    instance_count = int(data.get("min_instances", 1))
    prototype_count = int(data.get("prototype_count", 1))
    prototypes = []
    for index in range(prototype_count):
        prototype = _ensure_prim(stage, f"{data['path']}/Prototypes/Prototype_{index + 1}", "Cube")
        prototypes.append(prototype.GetPath())
    instancer.GetPrototypesRel().SetTargets(prototypes)
    instancer.GetProtoIndicesAttr().Set(
        Vt.IntArray([index % prototype_count for index in range(instance_count)])
    )
    instancer.GetPositionsAttr().Set(
        Vt.Vec3fArray(
            [Gf.Vec3f(float(index), 0.0, 0.0) for index in range(instance_count)]
        )
    )


def successful_usda(quest: Quest) -> str:
    """Return parseable USDA showing the target opinions for one room."""
    stage = Usd.Stage.CreateInMemory()
    root = stage.GetRootLayer()
    deferred_sublayers: list[str] | None = None
    notes: list[str] = [
        "USD Check: focused reference for the opinions this room grades.",
        "Paths and values are exact; ungraded scene content is intentionally omitted.",
    ]

    # Establish requested types first so built-in attributes carry their schema
    # types when later rules author values.
    for rule in quest.validator.get("assertions", []):
        name = _rule_name(rule)
        data = payload_for(rule, name)
        if name == "prim_type":
            _ensure_prim(stage, data["path"], str(data.get("value", data.get("expected", ""))))

    for rule in quest.validator.get("assertions", []):
        name = _rule_name(rule)
        data = payload_for(rule, name)
        path = data.get("path")
        expected = data.get("value", data.get("expected"))

        if name == "prim_exists":
            _ensure_prim(stage, path)
        elif name == "prim_type":
            continue
        elif name == "attribute_equals":
            _author_attribute(stage, path, data)
        elif name == "relationship_targets":
            prim_path, relationship_name = _property_path(path, data, "relationship")
            relationship = _ensure_prim(stage, prim_path).CreateRelationship(relationship_name)
            targets = [Sdf.Path(str(target)) for target in data.get("targets", expected or [])]
            relationship.SetTargets(targets)
        elif name == "metadata_equals":
            _author_metadata(stage, data)
        elif name == "kind_equals":
            Usd.ModelAPI(_ensure_prim(stage, path)).SetKind(str(expected))
        elif name == "active":
            _ensure_prim(stage, path).SetActive(True if expected is None else bool(expected))
        elif name == "instanceable":
            _ensure_prim(stage, path).SetInstanceable(True if expected is None else bool(expected))
        elif name == "specifier_equals":
            if str(expected) == "class":
                stage.CreateClassPrim(str(path))
            elif str(expected) == "over":
                stage.OverridePrim(str(path))
            else:
                _ensure_prim(stage, path)
        elif name == "has_reference":
            _ensure_prim(stage, path).GetReferences().AddReference(str(data.get("asset", "")))
        elif name == "has_payload":
            _ensure_prim(stage, path).GetPayloads().AddPayload(str(data.get("asset", "")))
        elif name == "has_inherit":
            source = stage.CreateClassPrim("/_USDCheck_InheritedClass")
            _ensure_prim(stage, path).GetInherits().AddInherit(source.GetPath())
        elif name == "has_specializes":
            source = _ensure_prim(stage, "/_USDCheck_SpecializesFallback")
            _ensure_prim(stage, path).GetSpecializes().AddSpecialize(source.GetPath())
        elif name == "has_variant_set":
            variant_set = _ensure_prim(stage, path).GetVariantSets().AddVariantSet(
                str(data.get("variant_set", data.get("name", "variant")))
            )
            for variant in data.get("variants", []):
                variant_set.AddVariant(str(variant))
            if data.get("selection"):
                variant_set.SetVariantSelection(str(data["selection"]))
        elif name == "sublayer_order":
            deferred_sublayers = [str(layer) for layer in data.get("layers", [])]
        elif name == "layer_offset":
            _ensure_prim(stage, path).GetReferences().AddReference(
                Sdf.Reference(
                    "source.usda",
                    layerOffset=Sdf.LayerOffset(
                        float(data.get("offset", 0)), float(data.get("scale", 1))
                    ),
                )
            )
        elif name == "traversal_contains":
            for included in data.get("paths", []):
                _ensure_prim(stage, included)
            for excluded in data.get("excluded", []):
                prim = stage.GetPrimAtPath(str(excluded))
                if prim and prim.IsValid():
                    prim.SetActive(False)
                else:
                    stage.CreateClassPrim(str(excluded))
        elif name == "default_prim":
            stage.SetDefaultPrim(_ensure_prim(stage, expected or path))
        elif name == "up_axis":
            UsdGeom.SetStageUpAxis(stage, str(expected))
        elif name == "meters_per_unit":
            UsdGeom.SetStageMetersPerUnit(stage, float(expected))
        elif name == "start_time":
            stage.SetStartTimeCode(float(expected))
        elif name == "end_time":
            stage.SetEndTimeCode(float(expected))
        elif name == "point_instancer":
            _author_point_instancer(stage, data)
        elif name == "attribute_source":
            notes.append(
                f"{path} must be authored in {data.get('layer')} so that layer is the strongest source."
            )
        elif name == "prim_stack":
            notes.append(
                f"{path} must compose at least {data.get('min', 1)} prim specs across layers."
            )
        else:
            notes.append(f"The {name} check also has to pass.")

    # Setting sublayers before authoring would try to compose files that only
    # exist in the challenge fixture. The authored root metadata is enough for
    # this focused reference.
    if deferred_sublayers is not None:
        root.subLayerPaths = deferred_sublayers

    text = root.ExportToString()
    comments = "\n".join(f"# {note}" for note in notes)
    return text.replace("#usda 1.0", f"#usda 1.0\n{comments}", 1)
