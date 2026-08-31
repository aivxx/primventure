"""Key Items: room-clear trophies and the Curio Desk that appraises them.

A trophy is any inventory entry that is not a consumable. Trading never removes
one. The desk stamps it instead, so the backpack keeps reading as a transcript
of the rooms a player cleared while the stamp records that its trade value is
already spent. Trophies buy the Saferoom's consumable bundles and nothing else,
which keeps Opinion Points the only currency bosses pay out.
"""
from __future__ import annotations

from typing import Any

from .models import PlayerState

CONSUMABLES = ("hint_tokens", "prim_censuses")

TROPHY_COSTS: dict[str, int] = {"hint_refill": 3, "prim_census": 4}


def is_trophy(name: str) -> bool:
    return name not in CONSUMABLES


def trophy_rows(state: PlayerState) -> list[tuple[str, int, int]]:
    """Every trophy in the order it was earned, as (name, held, stamped)."""
    return [
        (name, held, state.stamped_items.get(name, 0))
        for name, held in state.inventory.items()
        if is_trophy(name) and held > 0
    ]


def unstamped(state: PlayerState) -> int:
    return sum(max(held - stamped, 0) for _, held, stamped in trophy_rows(state))


def stamp(state: PlayerState, count: int) -> dict[str, int]:
    """Stamp `count` trophy units, oldest first, and report what was stamped."""
    stamped: dict[str, int] = {}
    remaining = count
    for name, held, already in trophy_rows(state):
        if remaining <= 0:
            break
        take = min(held - already, remaining)
        if take <= 0:
            continue
        state.stamped_items[name] = already + take
        stamped[name] = take
        remaining -= take
    return stamped


def desk(shop: dict[str, dict[str, Any]], state: PlayerState) -> dict[str, Any]:
    """The trade counter, priced off the same offers the Saferoom sells."""
    offers = {}
    for offer_id, cost in TROPHY_COSTS.items():
        offer = shop.get(offer_id)
        if offer is None:
            continue
        offers[offer_id] = {
            "name": offer["name"],
            "trophy_cost": cost,
            "inventory": dict(offer.get("inventory", {})),
        }
    rows = trophy_rows(state)
    return {
        "unstamped": unstamped(state),
        "held": sum(held for _, held, _ in rows),
        "offers": offers,
    }
