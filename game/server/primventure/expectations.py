"""Plain-language descriptions of what a room's validator checks.

The validator itself never reaches the client, but the *target state* has to.
Rooms are exercises in authoring USD, not in guessing which string the judge
wants, so every assertion is restated here as the end state the player is
aiming for.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _quote(value: Any) -> str:
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ", ".join(_quote(item) for item in value)
    return str(value)


def _join(items: list[Any]) -> str:
    return ", ".join(str(item) for item in items)


def _join_files(items: list[Any]) -> str:
    """Layer and asset lists read better without their directories."""
    return ", ".join(Path(str(item)).name for item in items)


def payload_for(rule: dict[str, Any], name: str) -> dict[str, Any]:
    """Assertions are written either as `name: value` or `name: {...}`."""
    payload = rule.get(name)
    if isinstance(payload, dict):
        return payload
    if payload is not None:
        return {"path": payload} if name == "prim_exists" else {"value": payload}
    return rule


def describe_assertion(rule: dict[str, Any]) -> str:
    name = str(rule.get("rule") or rule.get("type") or next(iter(rule), "unknown"))
    data = payload_for(rule, name)
    if data.get("message"):
        return str(data["message"])
    path = data.get("path", "")
    expected = data.get("value", data.get("expected"))

    if name == "prim_exists":
        return f"{path} exists on the stage"
    if name == "prim_type":
        return f"{path} is typed {expected}"
    if name == "attribute_equals":
        target = path if "." in str(path) else f"{path}.{data.get('attribute', '')}"
        at_time = f" at time {data['time']}" if "time" in data else ""
        return f"{target} is set to {_quote(expected)}{at_time}"
    if name == "relationship_targets":
        target = path if "." in str(path) else f"{path}.{data.get('relationship', '')}"
        qualifier = "targets exactly" if data.get("exact", True) else "includes targets"
        return f"{target} {qualifier} {_join(data.get('targets', expected or []))}"
    if name == "metadata_equals":
        key = data.get("metadata", data.get("key", "metadata"))
        field = f" field {data['field']}" if data.get("field") else ""
        holder = path or "The stage"
        return f"{holder} carries {key}{field} metadata {_quote(expected)}"
    if name == "kind_equals":
        return f"{path} has kind {expected}"
    if name == "has_reference":
        asset = data.get("asset")
        return f"{path} references {Path(str(asset)).name}" if asset else f"{path} has an authored reference"
    if name == "has_payload":
        asset = data.get("asset")
        return f"{path} payloads {Path(str(asset)).name}" if asset else f"{path} has an authored payload"
    if name == "has_inherit":
        return f"{path} inherits from a class"
    if name == "has_specializes":
        return f"{path} specializes another prim"
    if name == "has_variant_set":
        variant_set = data.get("variant_set", data.get("name", "a variant set"))
        detail = f"{path} has variant set {variant_set}"
        if data.get("variants"):
            detail += f" holding {_join(data['variants'])}"
        if data.get("selection"):
            detail += f", selected on {data['selection']}"
        return detail
    if name == "active":
        wanted = True if expected is None else bool(expected)
        return f"{path} is {'active' if wanted else 'deactivated'}"
    if name == "instanceable":
        wanted = True if expected is None else bool(expected)
        return f"{path} is {'instanceable' if wanted else 'not instanceable'}"
    if name == "specifier_equals":
        return f"{path} is authored as {expected}"
    if name == "prim_stack":
        detail = f"{path} composes at least {data.get('min', 1)} spec(s)"
        if data.get("specifiers"):
            detail += f" including {_join(data['specifiers'])}"
        return detail
    if name == "sublayer_order":
        layers = _join_files(data.get("layers", []))
        order = "exactly" if data.get("exact") else "starting with"
        return f"Root layer sublayers read {order} {layers} (strongest first)"
    if name == "layer_offset":
        parts = []
        if data.get("offset") is not None:
            parts.append(f"offset of {data['offset']}")
        if data.get("scale") is not None:
            parts.append(f"scale of {data['scale']}")
        return f"{path} carries a layer {' and '.join(parts) if parts else 'offset'}"
    if name == "attribute_source":
        return f"The strongest opinion for {path} comes from {Path(str(data.get('layer'))).name}"
    if name == "traversal_contains":
        detail = f"Traversal reaches {_join(data.get('paths', []))}"
        if data.get("excluded"):
            detail += f" and skips {_join(data['excluded'])}"
        return detail
    if name == "default_prim":
        return f"The stage default prim is {expected or path}"
    if name == "up_axis":
        return f"The stage up axis is {expected}"
    if name == "meters_per_unit":
        return f"The stage metersPerUnit is {expected}"
    if name == "point_instancer":
        detail = f"{path} is a PointInstancer with at least {data.get('min_instances', 1)} instance(s)"
        if data.get("prototype_count") is not None:
            detail += f" and {data['prototype_count']} prototype(s)"
        return detail
    if name == "start_time":
        return f"The stage start timeCode is {expected}"
    if name == "end_time":
        return f"The stage end timeCode is {expected}"
    return f"{name.replace('_', ' ')} holds for {path or 'the stage'}"


def describe_assertions(validator: dict[str, list[dict[str, Any]]]) -> list[str]:
    return [describe_assertion(rule) for rule in validator.get("assertions", [])]
