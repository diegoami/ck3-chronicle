"""A title's tenures, from its history and its own holder.

Ported from the POC's graph loader (``ck3graph.loader``), where it began; the
wiki's tenures come from it, and the graph add-on writes the same ones.
"""

from __future__ import annotations

from typing import Any

from .parser import Block
from .titles import normalize_history


def holder_intervals(
    history: Block | list[tuple[str, int | None, str | None]] | None,
    end_date: str | None,
    current_holder: int | None = None,
    holder_since: str | None = None,
) -> list[dict[str, Any]]:
    """Turn a title history into ``[{holder, from, to, open, reason}]``.

    Takes either a raw ``history`` block or the normalised tuples of a
    :class:`~ck3chronicle.core.titles.TitleRecord`. An entry with a holder opens a
    tenure and closes the running one; a terminal entry (``type=destroyed``)
    only closes, because its holder names the outgoing ruler.

    The title's own ``holder`` and ``date`` win over the history for the tenure
    in progress, because they disagree in real saves: 6 079 held titles have no
    history at all, and another 341 (all leased-out baronies) changed hands
    without an entry being appended. So ``holder_since`` opens the final tenure
    whenever the history does not already end with ``current_holder``.

    A tenure with no start date is dropped: it cannot be placed in time, and
    ``Title.holder`` still records who holds the title.
    """
    # NB: Block subclasses list, so it must be tested for first.
    if history is None:
        entries: list[tuple[str, int | None, str | None]] = []
    elif isinstance(history, Block):
        entries = normalize_history(history)
    else:
        entries = list(history)

    intervals: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for date, holder, reason in entries:
        if current is not None:
            current["to"] = date
            intervals.append(current)
            current = None
        if holder is not None:
            current = {"holder": holder, "from": date, "to": None, "open": False, "reason": reason}

    if current is not None and current_holder is not None and current["holder"] != current_holder:
        current["to"] = holder_since or end_date  # the current holder took over here
        intervals.append(current)
        current = None
    if current is not None:
        current["to"] = end_date
        current["open"] = True
        intervals.append(current)
    elif current_holder is not None and holder_since is not None:
        intervals.append(
            {"holder": current_holder, "from": holder_since, "to": end_date, "open": True, "reason": None}
        )
    return [iv for iv in intervals if iv["from"] is not None]
