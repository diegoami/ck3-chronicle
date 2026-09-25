"""``api.build``: progress, logging, results and the site's links."""

import json
import logging

import pytest

from ck3chronicle import api
from ck3chronicle.config import Config
from ck3chronicle.wiki.site import Site
from helpers import SUCCESSION_EDITS, make_save


def two_snapshots(tmp_path):
    saves = tmp_path / "saves"
    saves.mkdir()
    make_save(saves / "a_1100.ck3", date="1100.6.1", seed=7, random_count=100)
    make_save(saves / "b_1120.ck3", date="1120.1.1", seed=7, random_count=200, edits=SUCCESSION_EDITS)
    return saves


def test_build_reports_progress_step_by_step(tmp_path):
    seen = []
    result = api.build(two_snapshots(tmp_path), tmp_path / "site", progress=seen.append)
    assert [p.stage for p in seen] == ["start", "read", "read", "write", "done"]
    assert [p.step for p in seen] == [0, 1, 2, 3, 3] and {p.steps for p in seen} == {3}
    assert seen[1].message == "a_1100.ck3" and seen[1].run == "7-1-6-1-2"
    assert len(result.chronicles) == 1 and result.pages == result.chronicles[0]["pages"] > 0
    assert result.images_wanted >= result.images_missing > 0


def test_build_logs_instead_of_printing(tmp_path, caplog, capsys):
    caplog.set_level(logging.INFO, logger="ck3chronicle")
    api.build(two_snapshots(tmp_path), tmp_path / "site")
    assert capsys.readouterr() == ("", "")
    text = caplog.text
    assert "1 run(s) to build" in text and "with 2 immediate vassal(s)" in text
    assert "wrote 1 chronicle(s)" in text


def test_a_core_warning_is_logged_as_a_warning(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="ck3chronicle")
    saves = two_snapshots(tmp_path)
    with pytest.raises(api.BuildError, match="no chronicles could be built"):
        api.build(saves, tmp_path / "site", Config(title="k_nope"))
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert "warning: 'k_nope' is not in a_1100.ck3, skipped" in warnings


def test_nothing_to_build_is_a_build_error(tmp_path):
    with pytest.raises(api.BuildError, match="no .ck3 saves"):
        api.build(tmp_path, tmp_path / "site")
    with pytest.raises(api.BuildError, match="no run 'nope'"):
        api.build(two_snapshots(tmp_path), tmp_path / "site", run_id="nope")


def test_a_run_takes_its_own_configured_title(tmp_path):
    config = Config(title="k_nope", titles={"7-1-6-1-2": "c_test"})
    result = api.build(two_snapshots(tmp_path), tmp_path / "site", config)
    assert result.chronicles[0]["name"] != "k_nope"
    manifest = json.loads((tmp_path / "site" / "7-1-6-1-2" / "portraits.json").read_text(encoding="utf-8"))
    assert manifest["title"] == "c_test"


def test_the_site_carries_the_configured_links_and_no_others(tmp_path):
    site = Site(generator_name="Mine", generator_url="https://example.org/mine",
                companion_url="https://example.org/harvester", docs={"names": "https://example.org/rule"})
    out = tmp_path / "site"
    api.build(two_snapshots(tmp_path), out, Config(site=site))
    footer = '<a href="https://example.org/mine">Mine</a>'
    pages = [p for p in out.rglob("*.html")]
    assert pages and all(footer in p.read_text(encoding="utf-8") for p in pages)
    landing = (out / "index.html").read_text(encoding="utf-8")
    assert '<a href="https://example.org/harvester">harvester</a>' in landing
    for manifest in out.rglob("portraits.json"):
        assert json.loads(manifest.read_text(encoding="utf-8"))["docs"] == {"names": "https://example.org/rule"}
    everything = "".join(p.read_text(encoding="utf-8") for p in out.rglob("*") if p.is_file())
    assert "diegoami" not in everything


def test_without_a_companion_the_landing_page_names_none(tmp_path):
    out = tmp_path / "site"
    api.build(two_snapshots(tmp_path), out)
    landing = (out / "index.html").read_text(encoding="utf-8")
    assert "captured from the running game by" not in landing
    assert "Every image wanted, the missing ones included, is listed in" in landing
    assert '<a href="https://github.com/diegoami/ck3-chronicle">ck3-chronicle</a>' in landing


def test_the_log_stream_splits_lines_and_flushes_the_rest(caplog):
    caplog.set_level(logging.INFO, logger="ck3chronicle")
    stream = api._LogStream(logging.getLogger("ck3chronicle"))
    print("one\nwarning: two", file=stream, end="")
    assert [r.getMessage() for r in caplog.records] == ["one"]
    stream.flush()
    assert [(r.levelno, r.getMessage()) for r in caplog.records][-1] == (logging.WARNING, "warning: two")


# ---------------------------------------------------------------- saves that cannot be read

def test_an_unreadable_file_is_skipped_and_the_rest_built(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="ck3chronicle")
    saves = two_snapshots(tmp_path)
    (saves / "ironman.ck3").write_bytes(b"SAV0103\x00\x01binary tokens")
    (saves / "half-written.ck3").write_bytes((saves / "a_1100.ck3").read_bytes()[:900])
    result = api.build(saves, tmp_path / "site")
    assert [c["snapshots"] for c in result.chronicles] == [2]
    assert sorted(name for name, _ in result.skipped) == ["half-written.ck3", "ironman.ck3"]
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any(w.startswith("warning: cannot read ironman.ck3, skipped: first line") for w in warnings)


def test_a_save_unreadable_past_its_header_is_skipped_too(tmp_path):
    # the header and the first KB of the gamestate read fine; the parser meets
    # a `#` comment, which a save never carries, further in
    saves = two_snapshots(tmp_path)
    make_save(saves / "c_1130.ck3", date="1130.1.1", seed=7, random_count=300, edits=SUCCESSION_EDITS + (
        ('first_name="Vassal"', 'first_name="Vassal" # not in a save'),
    ))
    result = api.build(saves, tmp_path / "site")
    assert result.chronicles[0]["snapshots"] == 2
    assert [name for name, _ in result.skipped] == ["c_1130.ck3"]


def test_nothing_readable_is_a_build_error_that_says_why(tmp_path):
    folder = tmp_path / "saves"
    folder.mkdir()
    (folder / "ironman.ck3").write_bytes(b"SAV0103\x00\x01binary tokens")
    with pytest.raises(api.BuildError, match=r"no readable \.ck3 saves .* ironman\.ck3 \(first line"):
        api.build(folder, tmp_path / "site")
    with pytest.raises(api.BuildError, match=r"cannot read .*ironman\.ck3: first line"):
        api.build(folder / "ironman.ck3", tmp_path / "site")


# ---------------------------------------------------------------- choosing runs, cancelling

def three_runs(tmp_path):
    saves = tmp_path / "saves"
    saves.mkdir()
    for seed in (1, 2, 3):
        make_save(saves / f"run{seed}.ck3", seed=seed, random_count=100)
    return saves


def test_chosen_runs_are_built_into_one_landing_page(tmp_path):
    saves = three_runs(tmp_path)
    slugs = [r.slug for r in api.discover(saves)]
    result = api.build(saves, tmp_path / "site", run_ids=[slugs[0], slugs[2]])
    assert [c["slug"] for c in result.chronicles] == [slugs[0], slugs[2]]
    landing = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert slugs[0] in landing and slugs[2] in landing and slugs[1] not in landing
    with pytest.raises(api.BuildError, match="none of the chosen runs"):
        api.build(saves, tmp_path / "site", run_ids=["nope"])


def test_a_cancelled_build_stops_at_its_next_step(tmp_path):
    import threading

    saves = three_runs(tmp_path)
    cancel = threading.Event()
    seen = []

    def progress(p):
        seen.append(p.stage)
        if p.stage == "write":
            cancel.set()  # after the first chronicle

    with pytest.raises(api.Cancelled):
        api.build(saves, tmp_path / "site", progress=progress, cancel=cancel)
    assert seen == ["start", "read", "write"]
    assert not (tmp_path / "site" / "index.html").exists()  # no landing page for half a build
