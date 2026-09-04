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
    "Compositor": {},
    "Aggregator": {"hint_tokens": 1},
    "Exchanger": {"hint_tokens": 1},
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
HINT_CAP = 2
USD_CHECK_CAP = 2
AGGREGATOR_HINT_CAP = 3

CLASS_CATALOG: list[dict[str, Any]] = [
    {
        "id": "Compositor",
        "title": "Compositor",
        "blurb": "Layers, composition arcs, and competing opinions resolving into one stage.",
        "kit": "Declare and receive one free USD Check on each home floor.",
        "perks": [
            "Home: Opinion Quarter and Composition Highlands.",
            "City bosses +1 OP, floor bosses +2 OP on home floors.",
            "Home-floor boss misses charge half XP.",
            "One free USD Check after a fail per home floor.",
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
            "Assist restocks fill Hint Tokens to 3.",
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
        "kit": "Declare and receive 1 Hint Token.",
        "perks": [
            "Home: Customs Terminal.",
            "Assist restocks cost 1 OP.",
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


def assist_caps(state: PlayerState) -> dict[str, int]:
    hints = AGGREGATOR_HINT_CAP if state.specialization == "Aggregator" else HINT_CAP
    return {"hint_tokens": hints, "usd_checks": USD_CHECK_CAP}


def assists_full(state: PlayerState) -> bool:
    return all(state.inventory.get(name, 0) >= cap for name, cap in assist_caps(state).items())


def restock_assists(state: PlayerState) -> bool:
    """Fill Hint Tokens and USD Checks up to cap. False if both were already full."""
    if assists_full(state):
        return False
    for name, cap in assist_caps(state).items():
        state.inventory[name] = max(state.inventory.get(name, 0), cap)
    return True


def priced_shop(catalog: dict[str, dict[str, Any]], state: PlayerState) -> dict[str, dict[str, Any]]:
    shop = {key: dict(item) for key, item in catalog.items()}
    caps = assist_caps(state)
    spec = state.specialization
    if "hint_refill" in shop:
        shop["hint_refill"]["caps"] = caps
        shop["hint_refill"]["full"] = assists_full(state)
        shop["hint_refill"]["description"] = (
            f"Fills Hint Tokens to {caps['hint_tokens']} and USD Checks to "
            f"{caps['usd_checks']}."
            + (" Aggregator bulk rate." if spec == "Aggregator" else "")
        )
        if spec == "Exchanger":
            shop["hint_refill"]["cost"] = 1
    return shop


def claim_key(benefit: str, floor: int) -> str:
    return f"{benefit}:{floor}"


def consume_free_assist(state: PlayerState, quest: Quest, kind: str) -> bool:
    """Return True if this use is the class's free assist and claim it."""
    spec = state.specialization
    if kind == "hint" and spec != "Aggregator":
        return False
    if kind == "check" and spec != "Compositor":
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
    if kind == "check" and spec != "Compositor":
        return False
    if not is_home_floor(spec, quest.floor):
        return False
    return not state.benefit_claims.get(claim_key(f"free_{kind}", quest.floor))


def _holding_xp(xp: int) -> int:
    return xp - (xp // 100) * 100


BOSS_DEBT = 10


def _unused_exchanger_waiver(state: PlayerState, quest: Quest) -> bool:
    return (
        quest.kind.endswith("boss")
        and state.specialization == "Exchanger"
        and is_home_floor(state.specialization, quest.floor)
        and not state.benefit_claims.get(claim_key("boss_waiver", quest.floor))
    )


def boss_fee_for(state: PlayerState, quest: Quest) -> tuple[int, str]:
    if not quest.kind.endswith("boss"):
        return 0, "none"
    if _unused_exchanger_waiver(state, quest):
        state.benefit_claims[claim_key("boss_waiver", quest.floor)] = True
        return 0, "waiver"
    base = min(25, _holding_xp(state.xp))
    if base <= 0:
        return 0, "none"
    if not is_home_floor(state.specialization, quest.floor):
        return base, "standard"
    return max(1, base // 2), "home"


def preview_boss_fee(state: PlayerState, quest: Quest) -> tuple[int, str]:
    """Fee that would be charged, without mutating claims."""
    if not quest.kind.endswith("boss"):
        return 0, "none"
    if _unused_exchanger_waiver(state, quest):
        return 0, "waiver"
    base = min(25, _holding_xp(state.xp))
    if base <= 0:
        return 0, "none"
    if not is_home_floor(state.specialization, quest.floor):
        return base, "standard"
    return max(1, base // 2), "home"


def preview_boss_debt(state: PlayerState, quest: Quest) -> int:
    """Debt a miss would add after all fee waivers, without mutating state."""
    fee, kind = preview_boss_fee(state, quest)
    if (
        fee > 0
        or kind == "waiver"
        or _holding_xp(state.xp) > 0
        or not quest.kind.endswith("boss")
        or quest.id in state.completed_quests
        or state.boss_debts.get(quest.id, 0) > 0
    ):
        return 0
    return BOSS_DEBT


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
