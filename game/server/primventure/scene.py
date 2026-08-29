"""A renderable description of the composed city.

The client draws the stage itself rather than going through a glTF conversion.
Primventure's districts are built almost entirely from implicit Cube and Sphere
gprims, and glTF has no such concept, so a converter emits the transform
hierarchy and silently drops every shape — a city of 54 nodes and no geometry.
Sending the gprim parameters instead keeps the feed honest, needs no external
tool, and lets each cleared room show up as new blocks in the skyline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pxr import Usd, UsdGeom, UsdLux


# Muted concrete, so an unstyled district still reads as a building.
DEFAULT_COLOR = (0.58, 0.54, 0.66)
# Lights and empty lots are landmarks rather than geometry, so they carry their
# own palette instead of borrowing the concrete used for buildings.
LIGHT_COLOR = (1.0, 0.8, 0.18)
PAD_COLOR = (0.42, 0.36, 0.52)
# A published city is small; the cap only exists so a runaway PointInstancer
# prototype cannot hand the browser an unbounded payload.
MAX_PRIMS = 500


def _display_color(gprim: UsdGeom.Gprim) -> list[float]:
    attribute = gprim.GetDisplayColorAttr()
    value = attribute.Get() if attribute else None
    if value:
        return [round(float(channel), 4) for channel in value[0]]
    return [round(channel, 4) for channel in DEFAULT_COLOR]


def _triangles(mesh: UsdGeom.Mesh) -> list[int]:
    """Fan-triangulate whatever face sizes the room authored."""
    counts = mesh.GetFaceVertexCountsAttr().Get() or []
    indices = mesh.GetFaceVertexIndicesAttr().Get() or []
    triangles: list[int] = []
    cursor = 0
    for count in counts:
        face = [int(index) for index in indices[cursor : cursor + count]]
        cursor += count
        for corner in range(1, len(face) - 1):
            triangles += [face[0], face[corner], face[corner + 1]]
    return triangles


def _shape(prim: Usd.Prim, kind: str) -> dict[str, Any]:
    if kind == "Cube":
        size = UsdGeom.Cube(prim).GetSizeAttr().Get()
        return {"size": float(size if size is not None else 2.0)}
    if kind == "Sphere":
        radius = UsdGeom.Sphere(prim).GetRadiusAttr().Get()
        return {"radius": float(radius if radius is not None else 1.0)}
    if kind in {"Cylinder", "Cone", "Capsule"}:
        shape = getattr(UsdGeom, kind)(prim)
        radius = shape.GetRadiusAttr().Get()
        height = shape.GetHeightAttr().Get()
        axis = shape.GetAxisAttr().Get()
        return {
            "radius": float(radius if radius is not None else 1.0),
            "height": float(height if height is not None else 2.0),
            "axis": str(axis or "Z"),
        }
    if kind == "Mesh":
        mesh = UsdGeom.Mesh(prim)
        points = mesh.GetPointsAttr().Get() or []
        return {
            "points": [[round(float(value), 5) for value in point] for point in points],
            "triangles": _triangles(mesh),
        }
    return {}


def _is_light(prim: Usd.Prim) -> bool:
    if prim.HasAPI(UsdLux.LightAPI):
        return True
    # Older schema registrations do not always answer HasAPI for typed lights.
    return str(prim.GetTypeName()).endswith("Light")


def _light(prim: Usd.Prim) -> dict[str, Any]:
    """Lights carry no geometry, so the feed draws them from their own values."""
    intensity = prim.GetAttribute("inputs:intensity").Get()
    radius = prim.GetAttribute("inputs:radius").Get()
    color = prim.GetAttribute("inputs:color").Get()
    return {
        "intensity": float(intensity) if intensity is not None else 1.0,
        "radius": float(radius) if radius is not None else 0.5,
        "color": [round(float(channel), 4) for channel in (color or LIGHT_COLOR)],
    }


def _renders_below(prim: Usd.Prim) -> bool:
    """Whether anything under this prim already draws, pad included."""
    for descendant in Usd.PrimRange(prim):
        if descendant == prim:
            continue
        if descendant.IsA(UsdGeom.Gprim) or _is_light(descendant):
            return True
    return False


def world_scene(root_layer: Path) -> dict[str, Any]:
    """Every visible gprim and landmark on the composed stage, in world space."""
    empty: dict[str, Any] = {"up_axis": "Y", "meters_per_unit": 1.0, "prims": []}
    if not root_layer.exists():
        return empty
    stage = Usd.Stage.Open(str(root_layer))
    if stage is None:
        return empty
    transforms = UsdGeom.XformCache(Usd.TimeCode.Default())
    prims: list[dict[str, Any]] = []
    for prim in stage.Traverse():
        if len(prims) >= MAX_PRIMS:
            break
        imageable = UsdGeom.Imageable(prim)
        if imageable and imageable.ComputeVisibility() == UsdGeom.Tokens.invisible:
            continue
        kind = str(prim.GetTypeName())
        # Early floors teach lights, metadata, and time before they ever teach a
        # gprim, so the feed also carries the landmarks that prove that work:
        # lights as beacons, and an addressed-but-empty xform as a plot marker.
        if prim.IsA(UsdGeom.Gprim):
            detail = {
                "role": "geometry",
                "color": _display_color(UsdGeom.Gprim(prim)),
                **_shape(prim, kind),
            }
        elif _is_light(prim):
            detail = {"role": "light", **_light(prim)}
        elif prim.IsA(UsdGeom.Xformable) and not _renders_below(prim):
            detail = {"role": "pad", "color": [round(c, 4) for c in PAD_COLOR]}
        else:
            continue
        matrix = transforms.GetLocalToWorldTransform(prim)
        prims.append(
            {
                "path": str(prim.GetPath()),
                "name": prim.GetName(),
                "type": kind,
                # Row-major, matching USD's row-vector convention.
                "matrix": [round(float(matrix[row][column]), 5) for row in range(4) for column in range(4)],
                **detail,
            }
        )
    return {
        "up_axis": str(UsdGeom.GetStageUpAxis(stage)),
        "meters_per_unit": float(UsdGeom.GetStageMetersPerUnit(stage)),
        "prims": prims,
    }
