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

from pxr import Usd, UsdGeom


# Muted concrete, so an unstyled district still reads as a building.
DEFAULT_COLOR = (0.58, 0.54, 0.66)
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


def world_scene(root_layer: Path) -> dict[str, Any]:
    """Every visible gprim on the composed stage, in world space."""
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
        if not prim.IsA(UsdGeom.Gprim):
            continue
        imageable = UsdGeom.Imageable(prim)
        if imageable and imageable.ComputeVisibility() == UsdGeom.Tokens.invisible:
            continue
        kind = str(prim.GetTypeName())
        matrix = transforms.GetLocalToWorldTransform(prim)
        prims.append(
            {
                "path": str(prim.GetPath()),
                "type": kind,
                # Row-major, matching USD's row-vector convention.
                "matrix": [round(float(matrix[row][column]), 5) for row in range(4) for column in range(4)],
                "color": _display_color(UsdGeom.Gprim(prim)),
                **_shape(prim, kind),
            }
        )
    return {
        "up_axis": str(UsdGeom.GetStageUpAxis(stage)),
        "meters_per_unit": float(UsdGeom.GetStageMetersPerUnit(stage)),
        "prims": prims,
    }
