from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import RunRequest
from .runner import QuestRunner
from .store import ROOT, WORLD_DIR, QuestStore, SaveStore, quest_view


UPGRADES: dict[str, dict[str, Any]] = {
    "hint_refill": {
        "name": "Hint Token",
        "description": "Restocks two Hint Tokens in Consumables. Points at the room's lesson, never the answer.",
        "cost": 1,
        "inventory": {"hint_tokens": 2},
        "repeatable": True,
        "kind": "consumable",
    },
    "system_peek": {
        "name": "Opinion X-Ray",
        "description": "Restocks two Opinion X-Rays in Consumables. Inspects a cleared room's published layer.",
        "cost": 2,
        "inventory": {"system_peeks": 2},
        "repeatable": True,
        "kind": "consumable",
    },
    "deeper_hints": {
        "name": "Contextual Menace",
        "description": "Hints also name the relevant API. The answer still stays behind the curtain.",
        "cost": 2,
        "kind": "upgrade",
    },
    "boss_patience": {
        "name": "Executive Delay",
        "description": "The System pretends boss timers are longer. Timers remain flavor-only.",
        "cost": 1,
        "kind": "upgrade",
    },
    "title_licensed": {
        "name": "Licensed Opinionator",
        "description": "A cosmetic title of dubious regulatory standing.",
        "cost": 3,
        "title": "Licensed Opinionator",
        "kind": "upgrade",
    },
}

quests = QuestStore()
saves = SaveStore()
runner = QuestRunner(saves)

app = FastAPI(
    title="Primventure System API",
    version="0.1.0",
    description="Local usd-core arena for the Primventure certification crawl.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "composed", "quests": len(quests.all())}


@app.get("/api/state")
def get_state() -> dict[str, Any]:
    state = saves.load()
    return {
        **state.model_dump(),
        "next_level_xp": state.level * 100,
        "shop": UPGRADES,
    }


@app.get("/api/quests")
def get_quests() -> list[dict[str, Any]]:
    quests.refresh()
    state = saves.load()
    return [
        quest_view(quest, state, quests.lesson_for(quest))
        for quest in quests.all()
    ]


@app.get("/api/quests/{quest_id}")
def get_quest(quest_id: str) -> dict[str, Any]:
    quests.refresh()
    try:
        quest = quests.get(quest_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return quest_view(quest, saves.load(), quests.lesson_for(quest))


@app.get("/api/quests/{quest_id}/usda")
def get_quest_usda(quest_id: str) -> dict[str, str]:
    quests.refresh()
    try:
        quest = quests.get(quest_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return runner.usda_view(quest)


@app.get("/api/recipes")
def get_recipes() -> list[dict[str, Any]]:
    graph = ROOT / "docs" / "_static" / "data" / "glossary-graph-structure.js"
    text = graph.read_text() if graph.exists() else ""
    nodes = re.findall(
        r"\{\s*id:\s*'([^']+)',\s*label:\s*'([^']+)',\s*category:\s*'([^']+)'\s*\}",
        text,
    )
    unlocked = set(saves.load().recipes)
    return [
        {"id": identifier, "label": label, "category": category, "unlocked": identifier in unlocked}
        for identifier, label, category in nodes
    ]


@app.post("/api/quests/{quest_id}/run")
def run_quest(quest_id: str, request: RunRequest) -> dict[str, Any]:
    quests.refresh()
    try:
        quest = quests.get(quest_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    response = runner.run(quest, request).model_dump()
    # The runner only knows the saved player; clients expect the same enriched
    # state every other endpoint hands back, shop and level curve included.
    response["state"] = get_state()
    return response


@app.post("/api/quests/{quest_id}/hint")
def buy_hint(quest_id: str) -> dict[str, Any]:
    quests.refresh()
    try:
        quest = quests.get(quest_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    state = saves.load()
    if state.inventory.get("hint_tokens", 0) < 1:
        raise HTTPException(status_code=409, detail="No hint tokens remain.")
    state.inventory["hint_tokens"] -= 1
    saves.save(state)
    concepts = sorted(
        {
            str(rule.get("rule") or rule.get("type") or next(iter(rule), "stage"))
            for rule in quest.validator.get("assertions", [])
        }
    )
    depth = (
        " Inspect the authored layer before inspecting the composed prim."
        if "deeper_hints" in state.upgrades
        else ""
    )
    return {
        "hint": f"Review {', '.join(concepts)} in {quest.cookbook}.{depth}",
        "state": get_state(),
    }


@app.post("/api/quests/{quest_id}/peek")
def use_system_peek(quest_id: str) -> dict[str, Any]:
    quests.refresh()
    try:
        quest = quests.get(quest_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    state = saves.load()
    if quest.id not in state.completed_quests:
        raise HTTPException(
            status_code=409,
            detail="Clear this room before inspecting its published layer.",
        )
    if state.inventory.get("system_peeks", 0) < 1:
        raise HTTPException(status_code=409, detail="No System peeks remain.")
    if quest.world_target and not quest.world_target.startswith("/"):
        target = WORLD_DIR / quest.world_target
    else:
        bundle = WORLD_DIR / "workstreams" / quest.id
        target = next(
            (path for path in sorted(bundle.glob("submission.*")) if path.suffix in {".usd", ".usda", ".usdc"}),
            bundle / "submission.usd",
        )
    from pxr import Sdf

    layer = Sdf.Layer.FindOrOpen(str(target)) if target.exists() else None
    if layer is None:
        raise HTTPException(status_code=409, detail="The published layer could not be inspected.")
    state.inventory["system_peeks"] -= 1
    saves.save(state)
    return {
        "peek": {
            "layer": str(target.relative_to(ROOT)),
            "sublayers": list(layer.subLayerPaths),
            "message": "Authored layer inspected.",
        },
        "state": get_state(),
    }


@app.post("/api/shop/{upgrade_id}")
def buy_upgrade(upgrade_id: str) -> dict[str, Any]:
    upgrade = UPGRADES.get(upgrade_id)
    if upgrade is None:
        raise HTTPException(status_code=404, detail="The kiosk denies stocking that upgrade.")
    state = saves.load()
    if upgrade_id in state.upgrades and not upgrade.get("repeatable"):
        raise HTTPException(status_code=409, detail="Upgrade already installed.")
    if state.opinion_points < upgrade["cost"]:
        raise HTTPException(status_code=409, detail="Insufficient Opinion Points.")
    state.opinion_points -= upgrade["cost"]
    if upgrade_id not in state.upgrades:
        state.upgrades.append(upgrade_id)
    for item, count in upgrade.get("inventory", {}).items():
        state.inventory[item] = state.inventory.get(item, 0) + int(count)
    if "title" in upgrade:
        state.title = upgrade["title"]
    saves.save(state)
    return get_state()


@app.post("/api/specialization/{specialization}")
def choose_specialization(specialization: str) -> dict[str, Any]:
    choices = {"Compositor", "Aggregator", "Exchanger"}
    state = saves.load()
    if state.level < 2:
        raise HTTPException(status_code=409, detail="Crawler level 2 required.")
    if specialization not in choices:
        raise HTTPException(status_code=422, detail=f"Choose one of {sorted(choices)}.")
    if state.specialization and state.specialization != specialization:
        raise HTTPException(status_code=409, detail="Class path already chosen.")
    state.specialization = specialization
    saves.save(state)
    return get_state()


@app.post("/api/reset")
def reset_progress() -> dict[str, Any]:
    shutil.rmtree(WORLD_DIR / "workstreams", ignore_errors=True)
    shutil.rmtree(WORLD_DIR / ".preview", ignore_errors=True)
    (WORLD_DIR / "root.usda").write_text(
        '#usda 1.0\n(\n    documentation = "Primventure\\\'s persistent city. '
        'Successful quest layers are added here."\n)\n'
    )
    return saves.reset().model_dump()


@app.get("/api/world/tree")
def world_tree() -> dict[str, Any]:
    from pxr import Usd

    root = WORLD_DIR / "root.usda"
    if not root.exists():
        return {"name": "World", "path": "/World", "type": "Xform", "children": []}
    stage = Usd.Stage.Open(str(root))
    if stage is None:
        raise HTTPException(status_code=500, detail="Persistent world does not compose.")

    def node(prim: Any) -> dict[str, Any]:
        return {
            "name": prim.GetName(),
            "path": str(prim.GetPath()),
            "type": prim.GetTypeName() or "untyped",
            "active": prim.IsActive(),
            "instance": prim.IsInstance(),
            "children": [node(child) for child in prim.GetChildren()],
        }

    return {
        "name": "PseudoRoot",
        "path": "/",
        "type": "root",
        "children": [node(prim) for prim in stage.GetPseudoRoot().GetChildren()],
    }


@app.get("/api/world/preview")
def world_preview() -> FileResponse:
    source = WORLD_DIR / "root.usda"
    output = WORLD_DIR / ".preview" / "world.glb"
    if not source.exists():
        raise HTTPException(status_code=404, detail="Recapture a world layer first.")
    converter = shutil.which("usd2gltf")
    if converter is None:
        raise HTTPException(status_code=503, detail="usd2gltf command is unavailable.")
    output.parent.mkdir(parents=True, exist_ok=True)
    if not output.exists() or output.stat().st_mtime < source.stat().st_mtime:
        completed = subprocess.run(
            [converter, "-i", str(source), "-o", str(output)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode:
            raise HTTPException(status_code=500, detail=completed.stderr.strip())
    return FileResponse(output, media_type="model/gltf-binary", filename="primventure.glb")


docs_build = ROOT / "docs" / "_build" / "html"
if docs_build.exists():
    app.mount("/cookbook", StaticFiles(directory=docs_build, html=True), name="cookbook")

web_dist = ROOT / "game" / "web" / "dist"
if web_dist.exists():
    app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")

