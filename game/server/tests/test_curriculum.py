"""The crawl must be the Learn OpenUSD path, in the order Learn OpenUSD teaches it.

Rooms are adaptations of curriculum lessons, never inventions. These tests read
the real toctrees under docs/ and hold the catalog to them: every lesson gets a
room, no room cites a page the curriculum does not list, and a player never has
to author a concept whose lesson comes later in the path.
"""
from __future__ import annotations

import re
from pathlib import Path

from primventure.store import ROOT, QuestStore

DOCS = ROOT / "docs"
TOCTREE = re.compile(r"^:{3,}\{toctree\}\n(.*?)^:{3,}\s*$", re.S | re.M)
# Sidebar-only trees. Neither lists lessons, so neither can supply a room.
SIDEBARS = ("caption: Common Resources", "caption: Get Involved")
# Landing pages, environment setup, and Q&A appendices carry no authoring to grade.
UNTEACHABLE = {"index.md", "setup.md", "why-openusd-developer-certification.md"}


def _entries(page: Path) -> list[str]:
    found: list[str] = []
    for block in TOCTREE.findall(page.read_text(encoding="utf-8")):
        if any(sidebar in block for sidebar in SIDEBARS):
            continue
        for line in block.splitlines():
            line = line.strip()
            # Directive options, and `Overview <self>` pointing back at this page.
            if not line or line.startswith(":"):
                continue
            match = re.match(r"^(?:.*<(.+?)>|(.+))$", line)
            target = (match.group(1) or match.group(2)).strip()
            if target == "self" or target.startswith("http"):
                continue
            found.append(target)
    return found


def curriculum_order() -> list[str]:
    """Every Learn OpenUSD page, depth first, in the order the toctrees list it."""
    order: list[str] = []
    seen: set[str] = set()

    def walk(page: Path) -> None:
        for entry in _entries(page):
            base = page.parent / entry
            target = base.with_suffix(".md")
            if not target.is_file():
                target = base / "index.md"
            if not target.is_file():
                raise AssertionError(f"{page} lists {entry!r}, which is not on disk")
            relative = target.relative_to(ROOT).as_posix()
            if relative in seen:
                continue
            seen.add(relative)
            order.append(relative)
            if target.name == "index.md":
                walk(target)

    walk(DOCS / "index.md")
    return order


def teachable(order: list[str]) -> list[str]:
    return [
        page
        for page in order
        if Path(page).name not in UNTEACHABLE and "faq" not in Path(page).name
    ]


def test_every_room_adapts_a_page_the_curriculum_actually_lists() -> None:
    """A cookbook path off the toctree is a lesson Learn OpenUSD does not teach."""
    listed = set(curriculum_order())
    invented = sorted(
        {quest.cookbook for quest in QuestStore().all() if quest.cookbook not in listed}
    )
    assert not invented, invented


def test_every_curriculum_lesson_has_a_room() -> None:
    """Skipping a lesson breaks the path as surely as inventing one does."""
    covered = {quest.cookbook for quest in QuestStore().all()}
    missing = [page for page in teachable(curriculum_order()) if page not in covered]
    assert not missing, missing


def first_encounters() -> list[tuple[str, str]]:
    """The (room, lesson) pairs where the crawl introduces each lesson, in play order.

    A later room may revisit any lesson already introduced. Only the first time
    a page appears does it place that lesson in the path.
    """
    introduced: list[tuple[str, str]] = []
    seen: set[str] = set()
    for quest in QuestStore().all():
        if quest.cookbook in seen:
            continue
        seen.add(quest.cookbook)
        introduced.append((quest.id, quest.cookbook))
    return introduced


def test_lessons_are_introduced_in_curriculum_order() -> None:
    """Reaching a lesson early is teaching it early, whichever room does it.

    Bosses count. A boss that opens a page no earlier room has cited is the
    room where the player first meets that lesson.
    """
    rank = {page: index for index, page in enumerate(curriculum_order())}
    early: list[str] = []
    furthest = -1
    for quest_id, page in first_encounters():
        position = rank[page]
        if position < furthest:
            behind = [name for name, index in rank.items() if index == furthest][0]
            early.append(f"{quest_id} opens {page} after the crawl already reached {behind}")
        furthest = max(furthest, position)
    assert not early, early


# The lesson that teaches the authoring each validator rule grades. A room may
# only grade a rule once the crawl has reached that lesson.
#
# The page is the one that teaches what the *player* writes, not how the check
# reads it back. `traversal_contains` resolves through a stage traversal, but
# all the player authors is a prim, so it sits with the prims lesson.
RULE_LESSON: dict[str, str] = {
    "prim_exists": "docs/stage-setting/prims.md",
    "prim_type": "docs/stage-setting/prims.md",
    "attribute_equals": "docs/stage-setting/properties/attributes.md",
    "relationship_targets": "docs/stage-setting/properties/relationships.md",
    "start_time": "docs/stage-setting/timecodes-timesamples.md",
    "end_time": "docs/stage-setting/timecodes-timesamples.md",
    "metadata_equals": "docs/stage-setting/metadata.md",
    "traversal_contains": "docs/stage-setting/prims.md",
    # Layers is where an opinion first gets a layer to live in, which is all
    # these two rules read back.
    "sublayer_order": "docs/composition-basics/layers.md",
    "attribute_source": "docs/composition-basics/layers.md",
    "specifier_equals": "docs/composition-basics/specifiers.md",
    # GetPrimStack appears with `over`, where a prim first has more than one spec.
    "prim_stack": "docs/composition-basics/specifiers.md",
    "has_reference": "docs/composition-basics/references.md",
    "default_prim": "docs/composition-basics/default-prim.md",
    "has_variant_set": "docs/composition-basics/variant-sets.md",
    "active": "docs/beyond-basics/active-inactive-prims.md",
    "kind_equals": "docs/beyond-basics/model-kinds.md",
    "up_axis": "docs/beyond-basics/units.md",
    "meters_per_unit": "docs/beyond-basics/units.md",
    "layer_offset": "docs/creating-composition-arcs/sublayers/working-with-sublayers.md",
    "has_payload": "docs/creating-composition-arcs/references-payloads/working-with-payloads.md",
    "has_inherit": "docs/creating-composition-arcs/inherits-specializes/what-is-inherits.md",
    "has_specializes": "docs/creating-composition-arcs/inherits-specializes/what-is-specializes.md",
    "instanceable": (
        "docs/asset-modularity-instancing/authoring-scenegraph-instancing/"
        "scenegraph-instancing-intro.md"
    ),
    "point_instancer": (
        "docs/asset-modularity-instancing/authoring-point-instancing/point-instancing-intro.md"
    ),
}


# Authoring calls whose curriculum home is a single, identifiable page. A card
# may name one only once the path has reached the lesson that introduces it.
API_LESSON: dict[str, str] = {
    "SetDefaultPrim": "docs/composition-basics/default-prim.md",
    "AddReference": "docs/composition-basics/references.md",
    "AddVariantSet": "docs/composition-basics/variant-sets.md",
    "SetActive": "docs/beyond-basics/active-inactive-prims.md",
    "SetKind": "docs/beyond-basics/model-kinds.md",
    "SetStageUpAxis": "docs/beyond-basics/units.md",
    "SetStageMetersPerUnit": "docs/beyond-basics/units.md",
    "AddPayload": "docs/creating-composition-arcs/references-payloads/working-with-payloads.md",
    "AddInherit": "docs/creating-composition-arcs/inherits-specializes/what-is-inherits.md",
    "AddSpecialize": "docs/creating-composition-arcs/inherits-specializes/what-is-specializes.md",
    "SetInstanceable": (
        "docs/asset-modularity-instancing/authoring-scenegraph-instancing/"
        "scenegraph-instancing-intro.md"
    ),
}


def test_no_lesson_card_teaches_a_call_the_curriculum_introduces_later() -> None:
    """A card may only go as deep as the page it adapts.

    Floor 0's boss used to grade the default prim, and the reason nothing caught
    it is that the stage card taught `SetDefaultPrim` even though the stage page
    never mentions it. A card that runs ahead of its page teaches ahead of the
    path, and every audit reading card prose inherits the mistake.
    """
    rank = {page: index for index, page in enumerate(curriculum_order())}
    cards = QuestStore().lessons.all()
    ahead: list[str] = []
    for source, card in cards.items():
        if source not in rank:
            continue
        page = Path(ROOT / source).read_text(encoding="utf-8")
        prose = "\n".join(
            [card.objective, card.intro]
            + [beat.body for beat in card.beats]
            + [beat.code for beat in card.beats]
            + [point for beat in card.beats for point in beat.points]
        )
        for call, home in API_LESSON.items():
            if not re.search(rf"\b{call}\b", prose) or rank[home] <= rank[source]:
                continue
            # The page itself introducing the call settles it, whatever the order.
            if re.search(rf"\b{call}\b", page):
                continue
            ahead.append(f"{source} teaches {call}, which the path introduces in {home}")
    assert not ahead, sorted(ahead)


def test_every_validator_rule_maps_to_the_lesson_that_teaches_it() -> None:
    """A rule with no lesson behind it is authoring the curriculum never covers."""
    graded = {
        str(rule.get("rule") or rule.get("type") or next(iter(rule)))
        for quest in QuestStore().all()
        for rule in quest.validator.get("assertions", [])
    }
    assert not graded - set(RULE_LESSON), sorted(graded - set(RULE_LESSON))
    listed = set(curriculum_order())
    assert not set(RULE_LESSON.values()) - listed


def test_no_room_grades_authoring_the_path_has_not_reached() -> None:
    """Floor 0 may not ask for a default prim the path teaches on Floor 3.

    The bar is how far along the path the player stands when the room opens, not
    the room's own page, so a boss may grade every lesson behind it.
    """
    rank = {page: index for index, page in enumerate(curriculum_order())}
    ahead: list[str] = []
    reached = -1
    for quest in QuestStore().all():
        reached = max(reached, rank[quest.cookbook])
        for rule in quest.validator.get("assertions", []):
            name = str(rule.get("rule") or rule.get("type") or next(iter(rule)))
            if rank[RULE_LESSON[name]] > reached:
                ahead.append(f"{quest.id} grades {name}, first taught in {RULE_LESSON[name]}")
    assert not ahead, sorted(set(ahead))


def test_a_boss_never_opens_a_lesson_no_room_has_taught() -> None:
    """A boss consolidates authoring the player has already practised in a room."""
    kinds = {quest.id: quest.kind for quest in QuestStore().all()}
    unpractised = [
        f"{quest_id} is a boss opening {page} with no teaching room before it"
        for quest_id, page in first_encounters()
        if kinds[quest_id].endswith("boss")
    ]
    assert not unpractised, unpractised
