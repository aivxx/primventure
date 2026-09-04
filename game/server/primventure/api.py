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
    consume_free_assist,
    grant_starter_kit,
    priced_shop,
    recipe_is_affinity,
    restock_assists,
)
from .hints import hint_for
from .models import RunRequest
from .runner import QuestRunner
from .scene import world_scene
from .trophies import TROPHY_OP_COST, stamp, summary, unstamped
from .usd_check import successful_usda
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

SHOP: dict[str, dict[str, Any]] = {
    "hint_refill": {
        "name": "Assist Restock",
        "description": "Fills Hint Tokens and USD Checks to capacity.",
        "cost": 1,
        "repeatable": True,
        "kind": "consumable",
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
    shop = priced_shop(SHOP, state)
    return {
        # Saved source reaches the client per room through quest_view, so it stays
        # out of the state payload every poll refetches.
        **state.model_dump(exclude={"submissions", "last_fail"}),
        "next_level_xp": state.level * 100,
        "shop": shop,
        "class_benefits": class_payload(state),
        "trophies": summary(state),
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
    return {"hint": hint_for(quest, state), "state": get_state()}


@app.post("/api/quests/{quest_id}/debrief")
def review_boss_debrief(quest_id: str) -> dict[str, Any]:
    quests.refresh()
    try:
        quest = quests.get(quest_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    state = saves.load()
    fail = state.last_fail
    if (
        not quest.kind.endswith("boss")
        or fail is None
        or fail.quest_id != quest.id
        or quest.id in state.completed_quests
    ):
        raise HTTPException(status_code=409, detail="No boss debrief is waiting here.")
    checks = list(fail.failed_checks) or ["Recheck the room's validation checklist."]
    fail.debrief_required = False
    state.last_fail = fail
    saves.save(state)
    return {
        "checks": checks,
        "message": (
            "These are the requirements that failed. USD Check can show the "
            "focused USDA those graded opinions should produce."
        ),
        "state": get_state(),
    }


@app.post("/api/quests/{quest_id}/usd-check")
def run_usd_check(quest_id: str) -> dict[str, Any]:
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
            detail="Cleared rooms already have their accepted USDA review.",
        )
    if fail is None or fail.quest_id != quest.id:
        raise HTTPException(
            status_code=409,
            detail="Fail this room once before running USD Check.",
        )
    if not quest.validator.get("assertions"):
        raise HTTPException(
            status_code=409,
            detail="This briefing has no graded USDA to check.",
        )
    if not fail.paid:
        if not consume_free_assist(state, quest, "check"):
            if state.inventory.get("usd_checks", 0) < 1:
                raise HTTPException(
                    status_code=409,
                    detail="No USD Checks remain. Restock in the Saferoom.",
                )
            state.inventory["usd_checks"] = state.inventory.get("usd_checks", 0) - 1
        fail.paid = True
        state.last_fail = fail
        saves.save(state)
    return {
        "usda": successful_usda(quest),
        "state": get_state(),
    }


@app.post("/api/shop/{item_id}")
def buy_item(item_id: str) -> dict[str, Any]:
    if item_id not in SHOP:
        raise HTTPException(status_code=404, detail="The store does not stock that.")
    state = saves.load()
    offer = priced_shop(SHOP, state)[item_id]
    if item_id in state.upgrades and not offer.get("repeatable"):
        raise HTTPException(status_code=409, detail="Already in stock.")
    if state.opinion_points < offer["cost"]:
        raise HTTPException(status_code=409, detail="Insufficient Opinion Points.")
    if item_id == "hint_refill":
        if not restock_assists(state):
            raise HTTPException(status_code=409, detail="Consumables are already at capacity.")
        state.opinion_points -= offer["cost"]
        saves.save(state)
        return get_state()
    state.opinion_points -= offer["cost"]
    if item_id not in state.upgrades:
        state.upgrades.append(item_id)
    for item, count in offer.get("inventory", {}).items():
        state.inventory[item] = state.inventory.get(item, 0) + int(count)
    saves.save(state)
    return get_state()


@app.post("/api/trophies/cash-in")
def cash_in_trophies() -> dict[str, Any]:
    """Stamp three Key Items for one Opinion Point. The trophies stay in the bag."""
    state = saves.load()
    available = unstamped(state)
    if available < TROPHY_OP_COST:
        raise HTTPException(
            status_code=409,
            detail=f"Cashing in costs {TROPHY_OP_COST} unstamped Key Items and you have {available}.",
        )
    stamped = stamp(state, TROPHY_OP_COST)
    state.opinion_points += 1
    saves.save(state)
    return {"stamped": stamped, "granted": {"opinion_points": 1}, "state": get_state()}


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

