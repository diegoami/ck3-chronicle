"""One streaming pass over a save's character records: the whole population.

The wiki finds parents by **inverting** every child list, because a save stores
parentage downward only: `family_data` lists `child` and never `father` or
`mother` (Ck-parser's PLAN.md §10). That inversion costs a full pass and about 80 MB,
and it exists purely so Python can look *up* from a child.

A graph does not need it. `(:Character)-[:PARENT_OF]->(:Character)` is written
straight off each record's own child list, and Cypher walks the edge in either
direction:

    MATCH (c)<-[:PARENT_OF]-(parent)          // up, no inversion
    MATCH (c)-[:PARENT_OF*2]->(grandchild)    // down, any depth

So this module streams the character sections once, yielding what one record
contributes, and never holds more than one record at a time. The graph add-on
writes it in batches as it arrives.

It is public API: the add-on depends on the library, and needs nothing private
from it (Ck-parser#48). Ported from the POC's ``ck3graph.people``, with
:func:`character_props` from ``ck3graph.loader``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

from .container import open_gamestate_text
from .family import SECTIONS, own_family
from .parser import Block, PushbackLines, iter_children, to_date


def character_props(char_id: int, char: Block) -> dict[str, Any]:
    """Node properties for one character. Game dates become real ``date`` values.

    Save dates are strings like ``"1364.3.10"``, which sort lexicographically:
    ``"99.1.1"`` would land after ``"948.3.25"``. Everything written to the graph
    that is a game date is converted so that ordering and range queries work.
    """
    dead = char.get("dead_data")
    return {
        "id": char_id,
        "first_name": str(char.get("first_name", "")),
        "birth": to_date(char.get("birth")),
        "death": to_date(dead.get("date")) if isinstance(dead, Block) else None,
        "death_reason": str(dead.get("reason")) if isinstance(dead, Block) and dead.get("reason") else None,
        "female": bool(char.get("female", False)),
        "dynasty_house": char.get("dynasty_house"),
    }


@dataclass
class Person:
    """What one character record contributes to the graph."""

    id: int
    props: dict = field(default_factory=dict)
    children: list[int] = field(default_factory=list)
    spouses: list[int] = field(default_factory=list)
    former_spouses: list[int] = field(default_factory=list)
    #: A bastard's true father, when the save admits to one. Kept apart from
    #: `PARENT_OF` exactly as :mod:`ck3chronicle.core.family` keeps it apart from
    #: `parents`: the game distinguishes them, and so does the graph.
    real_father: int | None = None

    @property
    def house(self) -> int | None:
        value = self.props.get("dynasty_house")
        return value if isinstance(value, int) else None


def stream_people(save_path: str) -> Iterator[Person]:
    """Every character of one save, in section order, one record at a time.

    All three character sections are read and none may be skipped: a parent can
    be alive, dead-unprunable or dead-prunable. Nothing is filtered out here —
    a character with no house and no titles is still somebody's parent, and
    dropping them would break the very paths the graph exists to walk.
    """
    for section in SECTIONS:
        with open_gamestate_text(save_path) as lines:
            for key, char in iter_children(PushbackLines(lines), section):
                if not isinstance(char, Block):
                    continue
                try:
                    cid = int(key)
                except (TypeError, ValueError):
                    continue
                person = Person(id=cid, props=character_props(cid, char))
                family = char.get("family_data")
                if isinstance(family, Block):
                    own = own_family(cid, family)
                    person.children = own.children
                    person.spouses = own.spouses
                    person.former_spouses = own.former_spouses
                    person.real_father = own.real_father
                yield person
