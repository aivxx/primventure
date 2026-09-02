---
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

kernelspec:
  name: python3
  display_name: python3
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: '0.13'
    jupytext_version: 1.17.2
---

# Relationships

## What Is a Relationship?

{term}`Relationships <Relationship>` are the second kind of {term}`property <Property>` you can author on a {term}`prim <Prim>`. Where an {term}`attribute <Attribute>` stores data, such as a number, a color, or a list of points, a relationship stores links to other objects in the scene. Each object that a relationship points at is called a {term}`target <Target>`.

### How Does It Work?

A relationship has a name, is authored on a prim, and holds a list of {term}`paths <Path>`. Those paths are its targets. The prim that holds the relationship is where the link starts, and its targets are where the link lands:

```usda
def Cube "Cube_1"{
    rel material:binding = </World/Looks/GreenMat>
}
```

The relationship above is named `material:binding`, it is authored on `/World/Cube_1`, and it has a single target: `/World/Looks/GreenMat`. Read it as a sentence and it says, "this cube uses that material."

#### Why Target an Object Instead of Containing It?

The prim hierarchy is a single tree, and every prim has exactly one parent. That works well for containment, where a wheel belongs to a car, but many associations in a scene are not containment. A material typically lives under `/World/Looks` while the geometry that uses it lives elsewhere, and many prims may need that same material. Nesting cannot express that, and you would not want to copy the material into every prim that uses it.

Targets are how you express those associations. You author the material once, in one place, and every prim that needs it targets it. Because there is only ever one material, editing it updates every prim pointing at it. The hierarchy answers "what is part of what," while targets answer questions like "which material does this geometry use," "which lightweight stand-in should a viewport draw instead of this expensive prim," and "which prims belong to this group."

#### Why Not Store the Path as Text?

You could store `"/World/Looks/GreenMat"` in a string attribute, but USD would treat that value as text and nothing would keep it accurate. Because a target is a path, OpenUSD understands what it refers to and maintains it for you:

* **Targets survive namespace changes.** When a {term}`reference <Reference>` brings an asset into a scene under a new parent, OpenUSD applies {term}`path translation <Path Translation>` so that the targets authored inside the asset resolve against the composed scene. A binding authored as `/Looks/GreenMat` inside an asset resolves to `/Env/House_01/Looks/GreenMat` once composed, and you never edit the asset to make that happen.
* **Targets can be edited sparsely.** Relationship targets support {term}`list editing <List Editing>`, so a stronger {term}`layer <Layer>` can add or remove a single target instead of replacing the entire list.
* **Targets are discoverable.** Because OpenUSD knows which properties hold links, tools can walk relationships to determine what a prim depends on. This is what makes it possible to package an asset with everything it needs, or to find every prim that uses a given material.

#### One Relationship, Many Targets

A relationship's value is a list, so one relationship can target any number of prims. This makes a relationship a natural way to describe a set of prims that has nothing to do with where those prims sit in the hierarchy, such as the prims in a collection, the geometry a light should illuminate, or the members of a group.

```{note}
Unlike an attribute, a relationship has no data type. It is a way of declaring, at creation time, that the only use for a property is to record linkage information. Conceptually, it is like an attribute whose data type is a "link." This means you can _not_ use a relationship to connect two already-existing attributes. For that, you can use {term}`attribute connections <Connection>`.
```

### Working With Python

Here are a few Python commands to familiarize yourself as you work with relationships. You author a relationship on a prim with {usdcpp}`UsdPrim::CreateRelationship`, retrieve it later with {usdcpp}`UsdPrim::GetRelationship`, and then read or edit its targets.

```python
# Get the target paths of a relationship
UsdRelationship.GetTargets()

# Set the target paths for a relationship
UsdRelationship.SetTargets()

# Add a new target path to a relationship
UsdRelationship.AddTarget()

# Remove a target path from a relationship
UsdRelationship.RemoveTarget()
```

As with attributes, prefer the schema-specific methods when they exist. Built-in relationships have generated accessors, like {usdcpp}`UsdGeomImageable::GetProxyPrimRel`, which are clearer and less brittle than looking a relationship up by name.

## Examples

```{tip}
You can run these examples locally as Jupyter notebooks. See [How to Run Notebooks Locally](../../jupyter-notebook-setup.md) for setup instructions.
```

+++ {"tags": ["remove-cell"]}
>**NOTE**: Before starting make sure to run the cell below. This will install the relevant OpenUSD libraries that will be used through this notebook.
+++
```{code-cell}
:tags: [remove-input]
:test-tags: [relationships-setup]
from lousd.utils.visualization import DisplayUSD, DisplayCode
from lousd.utils.helperfunctions import create_new_stage
```

### Example 1: Binding a Material with a Relationship
Material binding is the relationship you will encounter most often. It is encoded as a relationship named `material:binding` whose target is a `UsdShade.Material`, and `UsdShade.MaterialBindingAPI` authors and reads it for you.

Below, GreenMat is the target of two cubes and RedMat is the target of one. Notice that the two green cubes share a single material prim rather than each carrying a copy of it. Change GreenMat and both cubes change with it.
```{code-cell}
:test-tags: [relationships-material-binding]
:emphasize-lines: 15-40

from pxr import Usd, UsdGeom, UsdShade, Gf, Sdf

file_path = "_assets/relationships_ex1.usda"
stage = create_new_stage(file_path)

world_xform: UsdGeom.Xform = UsdGeom.Xform.Define(stage, "/World")


cube_1: UsdGeom.Cube = UsdGeom.Cube.Define(stage, world_xform.GetPath().AppendPath("Cube_1"))
cube_2: UsdGeom.Cube = UsdGeom.Cube.Define(stage, world_xform.GetPath().AppendPath("Cube_2"))
UsdGeom.XformCommonAPI(cube_2).SetTranslate(Gf.Vec3d(5, 0, 0))
cube_3: UsdGeom.Cube = UsdGeom.Cube.Define(stage, world_xform.GetPath().AppendPath("Cube_3"))
UsdGeom.XformCommonAPI(cube_3).SetTranslate(Gf.Vec3d(10, 0, 0))

# Create typeless container for the materials
looks = stage.DefinePrim("/World/Looks")

# Create simple green material for preview
green: UsdShade.Material = UsdShade.Material.Define(stage, looks.GetPath().AppendPath("GreenMat"))
green_ps = UsdShade.Shader.Define(stage, green.GetPath().AppendPath("PreviewSurface"))
green_ps.CreateIdAttr("UsdPreviewSurface")
green_ps.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.0, 1.0, 0.0))
green.CreateSurfaceOutput().ConnectToSource(green_ps.ConnectableAPI(), "surface")

# Create simple red material for preview
red: UsdShade.Material = UsdShade.Material.Define(stage, looks.GetPath().AppendPath("RedMat"))
red_ps = UsdShade.Shader.Define(stage, red.GetPath().AppendPath("PreviewSurface"))
red_ps.CreateIdAttr("UsdPreviewSurface")
red_ps.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(1.0, 0.0, 0.0))
red.CreateSurfaceOutput().ConnectToSource(red_ps.ConnectableAPI(), "surface")

# Bind materials to Prims
UsdShade.MaterialBindingAPI.Apply(cube_1.GetPrim()).Bind(green)
UsdShade.MaterialBindingAPI.Apply(cube_2.GetPrim()).Bind(green)
UsdShade.MaterialBindingAPI.Apply(cube_3.GetPrim()).Bind(red)

# Verify by reading the direct binding
for prim in [cube_1, cube_2, cube_3]:
    mat = UsdShade.MaterialBindingAPI(prim).GetDirectBinding().GetMaterial()
    print(f"{prim.GetPath()} -> {mat.GetPath() if mat else 'None'}")

stage.Save()
```
```{code-cell}
:tags: [remove-input]
DisplayUSD(file_path, show_usd_code=True)
```

Look at the generated `.usda` above and you will see the binding written out as `rel material:binding = </World/Looks/GreenMat>`. The cube stores a link, not a material.

### Example 2: Using a Built‑in Relationship (proxyPrim)
Many built-in schemas declare their own relationships. `UsdGeom.Imageable` has `proxyPrim`, which targets a lightweight stand-in that a viewport can draw instead of an expensive prim. The two prims here are siblings, so nesting could never have connected them; the target is what ties one to the other.
```{code-cell}
:test-tags: [relationships-proxy-prim]
:emphasize-lines: 14-22

from pxr import Usd, UsdGeom

file_path = "_assets/relationships_ex2.usda"
stage = create_new_stage(file_path)

world_xform: UsdGeom.Xform = UsdGeom.Xform.Define(stage, "/World")

# Define a "high cost" Sphere Prim under the World Xform:
high: UsdGeom.Sphere = UsdGeom.Sphere.Define(stage, world_xform.GetPath().AppendPath("HiRes"))

# Define a "low cost" Cube Prim under World Xfrom
low: UsdGeom.Cube = UsdGeom.Cube.Define(stage, world_xform.GetPath().AppendPath("Proxy"))

UsdGeom.Imageable(high).GetPurposeAttr().Set("render")
UsdGeom.Imageable(low).GetPurposeAttr().Set("proxy")

# Author the proxy link on the render Prim
UsdGeom.Imageable(high).GetProxyPrimRel().SetTargets([low.GetPath()])

# Tools that honor proxyPrim should draw the proxy in preview
draw_prim = UsdGeom.Imageable(high).ComputeProxyPrim()  # returns Usd.Prim
print("Preview should draw:", str(draw_prim[0].GetPath() if draw_prim else high.GetPath()))

stage.Save()
```
```{code-cell}
:tags: [remove-input]
DisplayUSD(file_path, show_usd_code=True)
```

### Example 3: Grouping Prims with Multiple Targets
A relationship can hold as many targets as you need, which lets you describe a set of prims without moving any of them. Here a typeless `Group` prim gathers a sphere and a cube by targeting both.

Because `members` is not part of any schema, we author it with `custom=True`. Nothing in OpenUSD acts on a custom relationship, but the links are recorded in the layer and any tool that knows to look for `members` can read them back with {usdcpp}`UsdRelationship::GetTargets`.
```{code-cell}
:test-tags: [relationships-prim-collections]
:emphasize-lines: 15-25

from pxr import Usd, UsdGeom, Gf

file_path = "_assets/relationships_ex3.usda"
stage = create_new_stage(file_path)

world_xform: UsdGeom.Xform = UsdGeom.Xform.Define(stage, "/World")

# Define a sphere under the World Xform:
sphere: UsdGeom.Sphere = UsdGeom.Sphere.Define(stage, world_xform.GetPath().AppendPath("Sphere"))

# Define a cube under the World Xform and set it to be 5 units away from the sphere:
cube: UsdGeom.Cube = UsdGeom.Cube.Define(stage, world_xform.GetPath().AppendPath("Cube"))
UsdGeom.XformCommonAPI(cube).SetTranslate(Gf.Vec3d(5, 0, 0))

# Create typeless container for the group
group = stage.DefinePrim("/World/Group")

# Define the relationship
group.CreateRelationship("members", custom=True).SetTargets(
    [sphere.GetPath(), cube.GetPath()]
)

# List relationship targets
members_rel = group.GetRelationship("members")
print("Group members:", [str(p) for p in members_rel.GetTargets()])

stage.Save()
```
```{code-cell}
:tags: [remove-input]
DisplayUSD(file_path, show_usd_code=True)
```

## Key Takeaways

A relationship is a typeless property whose value is a list of paths, and each of those paths is a target. The prim holding the relationship is where the link starts, and its targets are what it points at.

Targets let you express associations that the prim hierarchy cannot, since a prim has only one parent but may need to point at many unrelated prims. Relationships enable robust encoding of these dependencies and associations, such as:

* Binding geometry to materials
* Grouping prims into collections
* Establishing connections in shading networks
* Associating scene elements with non-hierarchical links (e.g. material binding)

Using relationships instead of hard paths enhances:

* Non-destructive editing workflows
* Referencing and asset reuse across tools
* Collaborative workflows across teams

Relationships are a way to link scene elements while enabling non-destructive editing and cross-tool collaboration. They enhance the flexibility and scalability of OpenUSD-based pipelines.



