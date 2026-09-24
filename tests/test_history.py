"""A title's tenures. Ported from the POC's tests/test_graph.py (holder_intervals)."""

import os

from ck3chronicle.core.history import holder_intervals
from ck3chronicle.core.parser import parse_text
from ck3chronicle.core.snapshot import gather
from helpers import SUCCESSION_EDITS, fixture_text, make_save


def test_holder_intervals_from_fixture_history():
    hist = parse_text(fixture_text())["landed_titles"]["landed_titles"]["0"]["history"]
    assert holder_intervals(hist, end_date="1100.6.1") == [
        {"holder": 100, "from": "867.1.1", "to": "880.5.5", "open": False, "reason": None},
        # closed by the destroyed entry, which does NOT open a tenure for its holder
        {"holder": 101, "from": "880.5.5", "to": "900.1.1", "open": False, "reason": None},
        {"holder": 102, "from": "950.3.3", "to": "1090.2.1", "open": False, "reason": "created"},
        {"holder": 200, "from": "1090.2.1", "to": "1100.6.1", "open": True, "reason": None},
    ]


def test_a_title_with_no_history_gets_one_tenure_from_its_date():
    # 6 079 held titles in the sample save have no history at all
    assert holder_intervals(None, "1100.6.1", current_holder=5, holder_since="1080.1.1") == [
        {"holder": 5, "from": "1080.1.1", "to": "1100.6.1", "open": True, "reason": None}
    ]


def test_a_tenure_that_cannot_be_placed_in_time_is_dropped():
    # Title.holder still records who holds it
    assert holder_intervals(None, "1100.6.1", current_holder=5) == []
    assert holder_intervals(None, "1100.6.1") == []


def test_the_titles_own_holder_wins_over_a_stale_history():
    # leased-out baronies change hands without a history entry being appended
    assert holder_intervals(
        [("900.1.1", 1, "leased_out")], "1100.6.1", current_holder=2, holder_since="1050.1.1"
    ) == [
        {"holder": 1, "from": "900.1.1", "to": "1050.1.1", "open": False, "reason": "leased_out"},
        {"holder": 2, "from": "1050.1.1", "to": "1100.6.1", "open": True, "reason": None},
    ]


def test_a_history_ending_in_a_terminal_entry_leaves_no_open_tenure():
    ended = holder_intervals([("900.1.1", 1, None), ("950.1.1", None, "destroyed")], "1100.6.1", current_holder=1)
    assert ended == [{"holder": 1, "from": "900.1.1", "to": "950.1.1", "open": False, "reason": None}]


def test_a_later_snapshot_closes_the_tenure_an_earlier_one_saw_open(tmp_path):
    # what the POC's whole-run dry run checked on its HELD_BY edges
    early = make_save(tmp_path / "a_1100.ck3", date="1100.6.1", seed=7, random_count=100)
    late = make_save(tmp_path / "b_1120.ck3", date="1120.1.1", seed=7, random_count=200, edits=SUCCESSION_EDITS)
    with open(os.devnull, "w", encoding="utf-8") as log:
        views = [gather(str(p), "k_testland", log=log) for p in (early, late)]
    tenures = [
        holder_intervals(v.target.history, end_date=v.fp.date, current_holder=v.target.holder, holder_since=v.target.date)
        for v in views
    ]
    assert tenures[0][-1] == {"holder": 200, "from": "1090.2.1", "to": "1100.6.1", "open": True, "reason": None}
    assert tenures[1][-2] == {"holder": 200, "from": "1090.2.1", "to": "1110.5.5", "open": False, "reason": None}
    assert tenures[1][-1] == {"holder": 201, "from": "1110.5.5", "to": "1120.1.1", "open": True, "reason": None}
