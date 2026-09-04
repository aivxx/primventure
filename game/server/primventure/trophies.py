"""Key Items: room-clear trophies that cash in for Opinion Points.

A trophy is any inventory entry that is not a consumable. Cashing in never
removes one. The Saferoom stamps it instead, so the backpack keeps reading as a
transcript of the rooms a player cleared while the stamp records that its trade
value is already spent. Three unstamped trophies buy one Opinion Point, which is
the only way Key Items enter the consumable store's currency.
"""
from __future__ import annotations

from typing import Any

from .models import PlayerState

CONSUMABLES = ("hint_tokens", "usd_checks")

# Three unstamped trophies buy one Opinion Point.
TROPHY_OP_COST = 3


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


def summary(state: PlayerState) -> dict[str, Any]:
    """How many trophies can still buy Opinion Points."""
    rows = trophy_rows(state)
    return {
        "unstamped": unstamped(state),
        "held": sum(held for _, held, _ in rows),
        "op_cost": TROPHY_OP_COST,
    }
