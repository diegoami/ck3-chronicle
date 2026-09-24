"""One snapshot's view, and a directory resolved into one run.

Ported from the POC's tests/test_pipeline.py: the parts that are not the graph
load. What its dry runs checked through Cypher is checked here on the view.
"""

import os

import pytest

from ck3chronicle.core.runs import scan
from ck3chronicle.core.snapshot import collect_characters, gather, lineage, resolve_saves
from ck3chronicle.core.titles import build_index
from helpers import SUCCESSION_EDITS, make_save


def test_gather_reads_the_title_with_its_vassals(tmp_path):
    p = make_save(tmp_path / "a.ck3")
    log_path = tmp_path / "log"
    with open(log_path, "w", encoding="utf-8") as log:
        view = gather(str(p), "k_testland", log=log)
    err = log_path.read_text(encoding="utf-8")
    assert "with 2 immediate vassal(s)" in err
    assert "5 referenced, 5 found, 5 kept, 0 missing" in err
    assert view.keys == ["k_testland", "x_mc_0", "c_test"]
    assert view.fp.date == "1100.6.1"
    assert set(view.characters) == {100, 101, 102, 200, 201}


def test_no_vassals_narrows_to_one_title(tmp_path):
    p = make_save(tmp_path / "a.ck3")
    with open(os.devnull, "w", encoding="utf-8") as log:
        view = gather(str(p), "k_testland", with_vassals=False, log=log)
    assert view.keys == ["k_testland"] and view.vassals == []


def test_a_missing_title_is_a_key_error(tmp_path):
    p = make_save(tmp_path / "a.ck3")
    with open(os.devnull, "w", encoding="utf-8") as log, pytest.raises(KeyError):
        gather(str(p), "k_missing", log=log)


def test_collect_characters_reaches_every_section(tmp_path):
    p = make_save(tmp_path / "a.ck3")
    found = collect_characters(p, {200, 100, 300, 999999})
    assert set(found) == {200, 100, 300}  # living, dead_unprunable, dead_prunable
    assert str(found[300]["first_name"]) == "Prunable"


def test_pipeline_titles_match_the_index(tmp_path):
    index = build_index(make_save(tmp_path / "a.ck3"))
    assert [v.key for v in index.immediate_vassals("k_testland")] == ["x_mc_0", "c_test"]
    target, vassals = lineage(index, "k_testland", with_vassals=True)
    assert target.key == "k_testland" and [v.key for v in vassals] == ["x_mc_0", "c_test"]


def test_the_view_answers_the_same_with_and_without_a_digest(tmp_path):
    p = make_save(tmp_path / "a.ck3")
    wanted = {100, 200, 201, 202, 300}
    with open(os.devnull, "w", encoding="utf-8") as log:
        plain = gather(str(p), "k_testland", log=log)
        cached = gather(str(p), "k_testland", log=log, cache_dir=tmp_path / "cache")
    assert plain.digest is None and cached.digest is not None
    assert set(plain.find_characters(wanted)) == set(cached.find_characters(wanted)) == wanted
    assert set(plain.living_characters(wanted)) == set(cached.living_characters(wanted)) == {200, 201, 202}
    plain_family, cached_family = plain.family_index(wanted), cached.family_index(wanted)
    assert plain_family.family_of(200) == cached_family.family_of(200)
    assert plain_family.parents == cached_family.parents and plain_family.parents[200] == [102, 103]


# ---------------------------------------------------------------- whole runs


def _two_snapshots(tmp_path, **later):
    """One run, saved in 1100 and again in 1120 after a succession."""
    make_save(tmp_path / "a_1100.ck3", date="1100.6.1", real_date="126.2.21", seed=7, random_count=100)
    make_save(
        tmp_path / "b_1120.ck3",
        date="1120.1.1",
        real_date="126.2.26",
        seed=7,
        random_count=200,
        edits=later.pop("edits", SUCCESSION_EDITS),
        **later,
    )
    return tmp_path


def test_a_directory_resolves_to_its_run_oldest_first(tmp_path):
    log_path = tmp_path.parent / f"{tmp_path.name}.log"
    with open(log_path, "w", encoding="utf-8") as log:
        saves = resolve_saves(str(_two_snapshots(tmp_path)), log=log)
    assert [os.path.basename(s) for s in saves] == ["a_1100.ck3", "b_1120.ck3"]
    err = log_path.read_text(encoding="utf-8")
    assert "run 7-1.6.1.2-867.1.1" in err and "2 snapshot(s), oldest first" in err


def test_a_file_resolves_to_itself(tmp_path):
    p = make_save(tmp_path / "a.ck3")
    assert resolve_saves(str(p)) == [str(p)]


def test_an_ambiguous_directory_asks_for_a_run(tmp_path):
    make_save(tmp_path / "one.ck3", date="1100.6.1", seed=1, random_count=100)
    make_save(tmp_path / "two.ck3", date="1100.6.1", seed=2, random_count=100)
    with open(os.devnull, "w", encoding="utf-8") as log:
        with pytest.raises(LookupError, match="holds 2 runs; pick one with --run"):
            resolve_saves(str(tmp_path), log=log)
        # run ids carry the rules and dlc hashes, so that id is incomplete
        with pytest.raises(LookupError, match="2-867.1.1"):
            resolve_saves(str(tmp_path), run_id="2-867.1.1", log=log)


def test_a_named_run_resolves_to_that_run_only(tmp_path):
    make_save(tmp_path / "one.ck3", date="1100.6.1", seed=1, random_count=100)
    make_save(tmp_path / "two.ck3", date="1100.6.1", seed=2, random_count=100)
    wanted = next(r for r in scan(tmp_path, with_sha256=False) if r.random_seed == 2)
    with open(os.devnull, "w", encoding="utf-8") as log:
        saves = resolve_saves(str(tmp_path), run_id=wanted.run_id, log=log)
    assert [os.path.basename(s) for s in saves] == ["two.ck3"]


def test_an_empty_directory_is_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError, match="no .ck3 saves under"):
        resolve_saves(str(tmp_path))


def test_a_title_absent_from_one_snapshot_fails_only_that_snapshot(tmp_path):
    # dynamic titles vanish when destroyed; the snapshots that have it still read
    runs = _two_snapshots(tmp_path, edits=SUCCESSION_EDITS + (('key="c_test"', 'key="c_gone"'),))
    with open(os.devnull, "w", encoding="utf-8") as log:
        early, late = resolve_saves(str(runs), log=log)
        assert gather(early, "c_test", log=log).target.key == "c_test"
        with pytest.raises(KeyError):
            gather(late, "c_test", log=log)
