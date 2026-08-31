from __future__ import annotations

import re
import shutil
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .benefits import (
    CLASSES,
    class_payload,
    compose_title,
    consume_free_assist,
    grant_starter_kit,
    priced_shop,
    recipe_is_affinity,
)
from .models import RunRequest
from .runner import QuestRunner
from .scene import world_scene
from .trophies import desk, stamp, unstamped
from .store import (
    ROOT,
    WORLD_DIR,
    QuestStore,
    SaveStore,
    newest_world_mtime,
    quest_view,
    seed_world,
)


# A city with nothing published yet. Every cleared room sublayers itself in.
EMPTY_CITY = (
    '#usda 1.0\n(\n    documentation = "Primventure\'s persistent city. '
    'Successful quest layers are added here."\n)\n'
)

# Starting the server is the moment a player needs a city of their own.
seed_world(WORLD_DIR)

UPGRADES: dict[str, dict[str, Any]] = {
    "hint_refill": {
        "name": "Hint Token",
        "description": "Restocks two Hint Tokens in Consumables. Points at the room's lesson, never the answer.",
        "cost": 1,
        "inventory": {"hint_tokens": 2},
        "repeatable": True,
        "kind": "consumable",
    },
    "prim_census": {
        "name": "Prim Census",
        "description": (
            "Restocks two Prim Censuses. After a failed run, a census lists the prims "
            "USD actually composed with their specifiers, types, and kinds, plus the "
            "real value behind every failing check. Your stage, never the answer."
        ),
        "cost": 2,
        "inventory": {"prim_censuses": 2},
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
    if state.specialization and not state.benefit_claims.get("starter_kit"):
        grant_starter_kit(state)
        saves.save(state)
    shop = priced_shop(UPGRADES, state)
    return {
        # Saved source reaches the client per room through quest_view, so it stays
        # out of the state payload every poll refetches.
        **state.model_dump(exclude={"submissions", "last_fail"}),
        "next_level_xp": state.level * 100,
        "shop": shop,
        "class_benefits": class_payload(state),
        "curio": desk(shop, state),
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
    state = saves.load()
    unlocked = set(state.recipes)
    return [
        {
            "id": identifier,
            "label": label,
            "category": category,
            "unlocked": identifier in unlocked,
            "affinity": recipe_is_affinity(state.specialization, identifier)
            or recipe_is_affinity(state.specialization, label),
        }
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
    if consume_free_assist(state, quest, "hint"):
        saves.save(state)
    else:
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


@app.post("/api/quests/{quest_id}/census")
def read_prim_census(quest_id: str) -> dict[str, Any]:
    quests.refresh()
    try:
        quest = quests.get(quest_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    state = saves.load()
    fail = state.last_fail
    if quest.id in state.completed_quests:
        raise HTTPException(
            status_code=409,
            detail="Cleared rooms do not consume a Prim Census.",
        )
    if fail is None or fail.quest_id != quest.id:
        raise HTTPException(
            status_code=409,
            detail="Fail this room once before reading a Prim Census.",
        )
    if not fail.has_stage:
        raise HTTPException(
            status_code=409,
            detail=(
                "That run never authored a stage USD could open, so there is nothing to "
                "census. The error in the run output is the finding."
            ),
        )
    if not fail.paid:
        if not consume_free_assist(state, quest, "census"):
            if state.inventory.get("prim_censuses", 0) < 1:
                raise HTTPException(status_code=409, detail="No Prim Censuses remain.")
            state.inventory["prim_censuses"] -= 1
        fail.paid = True
        state.last_fail = fail
        saves.save(state)
    return {
        "census": {
            "stage": fail.stage,
            "prims": [node.model_dump() for node in fail.prims],
            "observations": [reading.model_dump() for reading in fail.observations],
            "truncated": fail.truncated,
        },
        "state": get_state(),
    }


@app.post("/api/shop/{upgrade_id}")
def buy_upgrade(upgrade_id: str) -> dict[str, Any]:
    upgrade = UPGRADES.get(upgrade_id)
    if upgrade is None:
        raise HTTPException(status_code=404, detail="The kiosk denies stocking that upgrade.")
    state = saves.load()
    offer = priced_shop(UPGRADES, state)[upgrade_id]
    if upgrade_id in state.upgrades and not offer.get("repeatable"):
        raise HTTPException(status_code=409, detail="Upgrade already installed.")
    if state.opinion_points < offer["cost"]:
        raise HTTPException(status_code=409, detail="Insufficient Opinion Points.")
    state.opinion_points -= offer["cost"]
    if upgrade_id not in state.upgrades:
        state.upgrades.append(upgrade_id)
    for item, count in offer.get("inventory", {}).items():
        state.inventory[item] = state.inventory.get(item, 0) + int(count)
    if "title" in offer:
        compose_title(state)
    saves.save(state)
    return get_state()


@app.post("/api/curio/{offer_id}")
def trade_trophies(offer_id: str) -> dict[str, Any]:
    """Pay for a consumable bundle in Key Items instead of Opinion Points."""
    state = saves.load()
    offer = desk(priced_shop(UPGRADES, state), state)["offers"].get(offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="The Curio Desk does not appraise that.")
    cost = offer["trophy_cost"]
    available = unstamped(state)
    if available < cost:
        raise HTTPException(
            status_code=409,
            detail=f"The desk wants {cost} unstamped Key Items and counts {available}.",
        )
    stamped = stamp(state, cost)
    for item, count in offer["inventory"].items():
        state.inventory[item] = state.inventory.get(item, 0) + int(count)
    saves.save(state)
    return {"stamped": stamped, "granted": offer["inventory"], "state": get_state()}


@app.post("/api/specialization/{specialization}")
def choose_specialization(specialization: str) -> dict[str, Any]:
    state = saves.load()
    if state.level < 2:
        raise HTTPException(status_code=409, detail="Crawler level 2 required.")
    if specialization not in CLASSES:
        raise HTTPException(status_code=422, detail=f"Choose one of {sorted(CLASSES)}.")
    if state.specialization and state.specialization != specialization:
        raise HTTPException(status_code=409, detail="Class path already chosen.")
    state.specialization = specialization
    grant_starter_kit(state)
    saves.save(state)
    return get_state()


@app.post("/api/reset")
def reset_progress(scope: Literal["city", "all"] = "all") -> dict[str, Any]:
    """Tear the city down, and on the wider scope the crawler's record with it.

    Demolishing the city without clearing the save leaves the rooms cleared but
    unpublished, which is the state a player wants when they would rather rebuild
    the skyline from reruns than start the crawl over.
    """
    seed_world(WORLD_DIR)
    shutil.rmtree(WORLD_DIR / "workstreams", ignore_errors=True)
    shutil.rmtree(WORLD_DIR / ".preview", ignore_errors=True)
    (WORLD_DIR / "root.usda").write_text(EMPTY_CITY)
    if scope == "all":
        saves.reset()
    return get_state()


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


@app.get("/api/world/scene")
def world_scene_view() -> dict[str, Any]:
    """Geometry for the City Feed, straight off the composed stage."""
    return world_scene(WORLD_DIR / "root.usda")


@app.get("/api/world/stamp")
def world_stamp() -> dict[str, float]:
    """When the city last changed, so a client can poll for a redraw."""
    return {"mtime": newest_world_mtime(WORLD_DIR)}


docs_build = ROOT / "docs" / "_build" / "html"
if docs_build.exists():
    app.mount("/cookbook", StaticFiles(directory=docs_build, html=True), name="cookbook")

web_dist = ROOT / "game" / "web" / "dist"
if web_dist.exists():
    app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")

