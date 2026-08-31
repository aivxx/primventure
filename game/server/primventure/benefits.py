"""Class paths: kits, home-floor perks, and shop identity.

Home floors use the quest `floor` field the UI already sorts on. Prototype Wilds
is floor 8 and Customs Terminal is floor 7 in that numbering, even though the
YAML filenames and quest-id prefixes are swapped.
"""
from __future__ import annotations

from typing import Any

from .models import PlayerState, Quest

CLASSES = ("Compositor", "Aggregator", "Exchanger")

HOME_FLOORS: dict[str, frozenset[int]] = {
    "Compositor": frozenset({3, 5}),
    "Aggregator": frozenset({6, 8}),
    "Exchanger": frozenset({7}),
}

HOME_NAMES: dict[str, tuple[str, ...]] = {
    "Compositor": ("Opinion Quarter", "Composition Highlands"),
    "Aggregator": ("Hierarchy Foundry", "Prototype Wilds"),
    "Exchanger": ("Customs Terminal",),
}

STARTER_KITS: dict[str, dict[str, int]] = {
    "Compositor": {"prim_censuses": 1},
    "Aggregator": {"hint_tokens": 1},
    "Exchanger": {"hint_tokens": 1, "prim_censuses": 1},
}

AFFINITY_MARKERS: dict[str, tuple[str, ...]] = {
    "Compositor": (
        "layer", "sublayer", "liverps", "livrps", "reference", "payload",
        "variant", "inherit", "specialize", "opinion", "composition",
        "prim stack", "property stack", "list editing",
    ),
    "Aggregator": (
        "assembly", "component", "kind", "model hierarchy", "instance",
        "pointinstancer", "point instancer", "encapsulation", "asset",
        "namespace", "group",
    ),
    "Exchanger": (
        "data exchange", "mesh", "gprim", "up axis", "metadata", "asset info",
        "metersperunit", "validation", "provenance",
    ),
}

RECIPE_DRIP_CAP = 5

CLASS_CATALOG: list[dict[str, Any]] = [
    {
        "id": "Compositor",
        "title": "Compositor",
        "blurb": "Layers, composition arcs, and competing opinions resolving into one stage.",
        "kit": "Declare and receive 1 Prim Census.",
        "perks": [
            "Home: Opinion Quarter and Composition Highlands.",
            "Census restocks cost 1 OP.",
            "City bosses +1 OP, floor bosses +2 OP on home floors.",
            "Home-floor boss misses charge half XP.",
            "One free census after a fail per home floor, even at zero stock.",
            "Affinity recipes pay +1 OP, up to 5 for the crawl.",
        ],
    },
    {
        "id": "Aggregator",
        "title": "Aggregator",
        "blurb": "Scalable assets: payloads, kinds, instancing, and inspectable workstreams.",
        "kit": "Declare and receive 1 Hint Token.",
        "perks": [
            "Home: Hierarchy Foundry and Prototype Wilds.",
            "Hint restocks grant 3 tokens instead of 2.",
            "City bosses +1 OP, floor bosses +2 OP on home floors.",
            "Home-floor boss misses charge half XP.",
            "One free Hint per home floor, even at zero stock.",
            "Affinity recipes pay +1 OP, up to 5 for the crawl.",
        ],
    },
    {
        "id": "Exchanger",
        "title": "Exchanger",
        "blurb": "Moving data between OpenUSD and other tools with honest units and validation.",
        "kit": "Declare and receive 1 Hint Token and 1 Prim Census.",
        "perks": [
            "Home: Customs Terminal.",
            "Hint and census restocks both cost 1 OP.",
            "Neighborhood bosses +1 OP, city bosses +2 OP on Customs Terminal.",
            "Home-floor boss misses charge half XP.",
            "The first Customs Terminal boss miss costs 0 XP.",
            "Affinity recipes pay +1 OP, up to 5 for the crawl.",
        ],
    },
]


def is_home_floor(specialization: str | None, floor: int) -> bool:
    if not specialization:
        return False
    return floor in HOME_FLOORS.get(specialization, ())


def home_boss_bonus(specialization: str | None, quest: Quest) -> int:
    if not is_home_floor(specialization, quest.floor):
        return 0
    kind = quest.kind
    if specialization in {"Compositor", "Aggregator"}:
        if kind == "city_boss":
            return 1
        if kind == "floor_boss":
            return 2
        return 0
    if specialization == "Exchanger":
        if kind == "neighborhood_boss":
            return 1
        if kind == "city_boss":
            return 2
    return 0


def recipe_is_affinity(specialization: str | None, recipe: str) -> bool:
    if not specialization:
        return False
    haystack = recipe.lower().replace("_", " ").replace("-", " ")
    return any(marker in haystack for marker in AFFINITY_MARKERS.get(specialization, ()))


def grant_starter_kit(state: PlayerState) -> PlayerState:
    if not state.specialization or state.benefit_claims.get("starter_kit"):
        return state
    for item, count in STARTER_KITS[state.specialization].items():
        state.inventory[item] = state.inventory.get(item, 0) + count
    state.benefit_claims["starter_kit"] = True
    compose_title(state)
    return state


def compose_title(state: PlayerState) -> None:
    licensed = "title_licensed" in state.upgrades
    base = "Licensed Opinionator" if licensed else "Unlicensed Primwright"
    state.title = f"{state.specialization} · {base}" if state.specialization else base


def priced_shop(catalog: dict[str, dict[str, Any]], state: PlayerState) -> dict[str, dict[str, Any]]:
    shop = {key: dict(item) for key, item in catalog.items()}
    for item in shop.values():
        if "inventory" in item:
            item["inventory"] = dict(item["inventory"])
    spec = state.specialization
    if spec == "Compositor" and "prim_census" in shop:
        shop["prim_census"]["cost"] = 1
        shop["prim_census"]["description"] = (
            "Restocks two Prim Censuses. After a failed run, a census lists the prims "
            "USD actually composed and the real value behind every failing check. "
            "Compositor rate: 1 OP."
        )
    if spec == "Aggregator" and "hint_refill" in shop:
        shop["hint_refill"]["inventory"] = {"hint_tokens": 3}
        shop["hint_refill"]["description"] = (
            "Restocks three Hint Tokens. Aggregator bulk rate."
        )
    if spec == "Exchanger":
        if "hint_refill" in shop:
            shop["hint_refill"]["cost"] = 1
        if "prim_census" in shop:
            shop["prim_census"]["cost"] = 1
            shop["prim_census"]["description"] = (
                "Restocks two Prim Censuses. After a failed run, a census lists the prims "
                "USD actually composed and the real value behind every failing check. "
                "Exchanger rate: 1 OP."
            )
    return shop


def claim_key(benefit: str, floor: int) -> str:
    return f"{benefit}:{floor}"


def consume_free_assist(state: PlayerState, quest: Quest, kind: str) -> bool:
    """Return True if this use is the class's free assist and claim it."""
    spec = state.specialization
    if kind == "hint" and spec != "Aggregator":
        return False
    if kind == "census" and spec != "Compositor":
        return False
    if not is_home_floor(spec, quest.floor):
        return False
    key = claim_key(f"free_{kind}", quest.floor)
    if state.benefit_claims.get(key):
        return False
    state.benefit_claims[key] = True
    return True


def free_assist_available(state: PlayerState, quest: Quest, kind: str) -> bool:
    spec = state.specialization
    if kind == "hint" and spec != "Aggregator":
        return False
    if kind == "census" and spec != "Compositor":
        return False
    if not is_home_floor(spec, quest.floor):
        return False
    return not state.benefit_claims.get(claim_key(f"free_{kind}", quest.floor))


def _holding_xp(xp: int) -> int:
    return xp - (xp // 100) * 100


def boss_fee_for(state: PlayerState, quest: Quest) -> tuple[int, str]:
    base = min(25, _holding_xp(state.xp))
    if not quest.kind.endswith("boss") or base <= 0:
        return 0, "none"
    if not is_home_floor(state.specialization, quest.floor):
        return base, "standard"
    waiver_key = claim_key("boss_waiver", quest.floor)
    if state.specialization == "Exchanger" and not state.benefit_claims.get(waiver_key):
        state.benefit_claims[waiver_key] = True
        return 0, "waiver"
    return base // 2, "home"


def preview_boss_fee(state: PlayerState, quest: Quest) -> tuple[int, str]:
    """Fee that would be charged, without mutating claims."""
    base = min(25, _holding_xp(state.xp))
    if not quest.kind.endswith("boss") or base <= 0:
        return 0, "none"
    if not is_home_floor(state.specialization, quest.floor):
        return base, "standard"
    waiver_key = claim_key("boss_waiver", quest.floor)
    if state.specialization == "Exchanger" and not state.benefit_claims.get(waiver_key):
        return 0, "waiver"
    return base // 2, "home"


def recipe_bonus(state: PlayerState, recipes: list[str]) -> int:
    if not state.specialization or state.recipe_drip_op >= RECIPE_DRIP_CAP:
        return 0
    gained = 0
    already = set(state.recipes)
    for recipe in recipes:
        if recipe in already:
            continue
        if not recipe_is_affinity(state.specialization, recipe):
            continue
        if state.recipe_drip_op + gained >= RECIPE_DRIP_CAP:
            break
        gained += 1
    return gained


def class_payload(state: PlayerState) -> dict[str, Any]:
    spec = state.specialization
    return {
        "catalog": CLASS_CATALOG,
        "home_floors": sorted(HOME_FLOORS.get(spec, ())) if spec else [],
        "home_names": list(HOME_NAMES.get(spec, ())) if spec else [],
        "recipe_drip_op": state.recipe_drip_op,
        "recipe_drip_cap": RECIPE_DRIP_CAP,
        "claims": dict(state.benefit_claims),
    }
