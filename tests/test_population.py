"""Every character of a save, streamed. Ported from the POC's tests/test_graph.py.

The POC checked these through the Cypher its loader wrote; here they are
checked on what the stream yields, which is all the graph add-on gets.
"""

from datetime import date

from ck3chronicle.core.population import Person, character_props, stream_people
from ck3chronicle.core.parser import parse_text
from helpers import fixture_text, make_save


def test_nobody_is_filtered_out(tmp_path):
    # a filler character is still somebody's parent; all three sections are read
    people = list(stream_people(make_save(tmp_path / "a.ck3")))
    ids = [p.id for p in people]
    assert len(ids) == len(set(ids)) == 13
    assert {9001, 9002, 300, 100, 200} <= set(ids)  # filler, prunable, unprunable, living


def test_parentage_comes_downward_and_needs_no_inversion(tmp_path):
    # the save lists children and never parents; nothing is inverted here the
    # way ck3chronicle.core.family has to
    links = sorted(
        (p.id, child) for p in stream_people(make_save(tmp_path / "a.ck3")) for child in p.children
    )
    # both parents claim both children, and each claim is its own link; the
    # previous holder claims his successor and the sibling passed over
    assert links == [
        (102, 200), (103, 200), (103, 205),
        (200, 203), (200, 204), (202, 203), (202, 204),
    ]


def test_a_marriage_is_named_by_both_records(tmp_path):
    people = {p.id: p for p in stream_people(make_save(tmp_path / "a.ck3"))}
    assert people[200].spouses == [202] and people[202].spouses == [200]


def test_game_dates_become_real_dates():
    # "99.1.1" sorts after "948.3.25" as text; a date does not
    top = parse_text(fixture_text())
    props = character_props(100, top["dead_unprunable"]["100"])
    assert props["birth"] == date(830, 1, 1)
    assert props["death"] == date(880, 5, 5) and props["death_reason"] == "death_natural_causes"
    living = character_props(200, top["living"]["200"])
    assert living["death"] is None and living["death_reason"] is None
    assert living["female"] is False and living["dynasty_house"] == 500


def test_a_person_knows_their_house_only_when_it_is_a_number():
    assert Person(id=1, props={"dynasty_house": 500}).house == 500
    assert Person(id=1, props={}).house is None
