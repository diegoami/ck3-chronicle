"""The desktop edition: its folders, its session logic, and the window itself."""

import json
import logging
import time
from pathlib import Path

import pytest

from ck3chronicle import api
from ck3chronicle.config import Config
from ck3chronicle.gui import main, paths, session
from helpers import SUCCESSION_EDITS, make_save


# ---------------------------------------------------------------- folders


def test_saves_are_where_the_game_writes_them(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setattr(paths, "_known_folder", lambda folder_id: Path("D:/OneDrive/Documents"))
    assert paths.default_saves_dir("win32", {}, home) == (
        Path("D:/OneDrive/Documents") / "Paradox Interactive" / "Crusader Kings III" / "save games"
    )  # the shell's Documents, wherever OneDrive moved it
    assert paths.default_saves_dir("darwin", {}, home) == (
        home / "Documents" / "Paradox Interactive" / "Crusader Kings III" / "save games"
    )
    assert paths.default_saves_dir("linux", {}, home) == (
        home / ".local" / "share" / "Paradox Interactive" / "Crusader Kings III" / "save games"
    )
    assert paths.default_output_dir("darwin", {}, home) == home / "Documents" / "CK3 Chronicles"


def test_without_the_shell_documents_falls_back_to_the_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_known_folder", lambda folder_id: None)
    assert paths.documents_dir("win32", {"USERPROFILE": str(tmp_path)}, tmp_path / "x") == tmp_path / "Documents"


def test_app_data_is_the_users_never_the_programs(tmp_path):
    env = {"LOCALAPPDATA": str(tmp_path / "Local"), "APPDATA": str(tmp_path / "Roaming")}
    assert paths.cache_dir(platform="win32", env=env) == tmp_path / "Local" / "ck3-chronicle" / "cache"
    assert paths.settings_path(platform="win32", env=env) == tmp_path / "Roaming" / "ck3-chronicle" / "desktop.json"
    assert paths.log_path(platform="linux", env={}, home=tmp_path).parts[-4:] == (".cache", "ck3-chronicle", "logs", "last-build.log")
    assert paths.config_path(platform="linux", env={"XDG_CONFIG_HOME": str(tmp_path)}) == tmp_path / "ck3-chronicle" / "ck3chronicle.toml"


def test_the_known_folder_call_answers_on_windows_or_says_nothing():
    found = paths._known_folder(paths._DOCUMENTS)
    import sys

    if sys.platform == "win32":
        assert found is not None and found.is_dir()
    else:
        assert found is None


# ---------------------------------------------------------------- the playthrough list


def saves_folder(tmp_path):
    saves = tmp_path / "saves"
    saves.mkdir()
    make_save(saves / "a_1100.ck3", date="1100.6.1", seed=7, random_count=100)
    make_save(saves / "b_1120.ck3", date="1120.1.1", seed=7, random_count=200, edits=SUCCESSION_EDITS)
    make_save(saves / "other.ck3", date="1066.9.15", seed=9, random_count=100)
    return saves


def test_a_folder_lists_its_playthroughs_cheaply(tmp_path):
    rows, skipped = session.scan_folder(saves_folder(tmp_path))
    assert [(r.saves, r.years, r.version) for r in rows] == [(2, "1100\u20131120", "1.6.1.2"), (1, "1066", "1.6.1.2")]
    assert all(r.character for r in rows) and skipped == []
    assert [r.key for r in rows] == [run.slug for run in api.discover(tmp_path / "saves")]


def test_a_folder_problem_is_a_sentence(tmp_path):
    with pytest.raises(session.FolderProblem, match="does not exist"):
        session.scan_folder(tmp_path / "nope")
    (tmp_path / "empty").mkdir()
    with pytest.raises(session.FolderProblem, match=r"no Crusader Kings III saves \(\.ck3 files\)"):
        session.scan_folder(tmp_path / "empty")
    (tmp_path / "empty" / "ironman.ck3").write_bytes(b"SAV0103 binary")
    with pytest.raises(session.FolderProblem, match="None of the 1 save file"):
        session.scan_folder(tmp_path / "empty")


def test_unreadable_files_are_listed_beside_the_playthroughs(tmp_path):
    saves = saves_folder(tmp_path)
    (saves / "ironman.ck3").write_bytes(b"SAV0103 binary")
    rows, skipped = session.scan_folder(saves)
    assert len(rows) == 2 and [name for name, _ in skipped] == ["ironman.ck3"]


# ---------------------------------------------------------------- remembered choices, settings


def test_settings_survive_a_restart_and_a_bad_file(tmp_path):
    path = tmp_path / "desktop.json"
    first = session.Settings.load(path)
    assert first.saves == paths.default_saves_dir()
    first.saves, first.output, first.unticked = tmp_path / "s", tmp_path / "o", {"x"}
    first.save(path)
    again = session.Settings.load(path)
    assert (again.saves, again.output, again.unticked) == (tmp_path / "s", tmp_path / "o", {"x"})
    path.write_text("{ not json", encoding="utf-8")
    assert session.Settings.load(path).saves == paths.default_saves_dir()


def test_the_desktop_keeps_its_cache_in_app_data(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "cache_dir", lambda **kw: tmp_path / "appcache")
    assert session.desktop_config(tmp_path / "none.toml").cache == tmp_path / "appcache"
    toml = tmp_path / "ck3chronicle.toml"
    toml.write_text('[site]\ngenerator_name = "Mine"\n[cache]\ndir = "elsewhere"\n', encoding="utf-8")
    config = session.desktop_config(toml)
    assert config.site.generator_name == "Mine" and config.cache == tmp_path / "elsewhere"
    toml.write_text("[sight]\n", encoding="utf-8")
    with pytest.raises(session.FolderProblem, match="cannot be used"):
        session.desktop_config(toml)


def test_an_output_folder_with_other_files_is_asked_about(tmp_path):
    assert session.output_warning(tmp_path / "new") is None
    (tmp_path / "empty").mkdir()
    assert session.output_warning(tmp_path / "empty") is None
    (tmp_path / "busy").mkdir()
    (tmp_path / "busy" / "thesis.docx").write_bytes(b"x")
    assert session.output_warning(tmp_path / "busy").endswith("?")
    (tmp_path / "busy" / "portraits.json").write_text("{}", encoding="utf-8")
    assert session.output_warning(tmp_path / "busy") is None  # an earlier build
    (tmp_path / "file").write_bytes(b"x")
    assert "is a file" in session.output_warning(tmp_path / "file")


# ---------------------------------------------------------------- the build job


def drain(job: session.BuildJob, timeout: float = 60) -> list[tuple]:
    job.thread.join(timeout)
    assert not job.running
    events = []
    while not job.events.empty():
        events.append(job.events.get_nowait())
    return events


def test_a_build_job_reports_progress_logs_and_its_result(tmp_path):
    saves = saves_folder(tmp_path)
    rows, _ = session.scan_folder(saves)
    log_file = tmp_path / "logs" / "last-build.log"
    job = session.BuildJob(saves, tmp_path / "out", [rows[0].key], Config(cache=tmp_path / "c"), log_file).start()
    events = drain(job)
    kinds = [e[0] for e in events]
    assert kinds[-1] == "done" and "progress" in kinds and "log" in kinds
    result = events[-1][1]
    assert [c["slug"] for c in result.chronicles] == [rows[0].key]
    assert session.has_chronicle(tmp_path / "out")
    assert "wrote 1 chronicle(s)" in log_file.read_text(encoding="utf-8")
    assert not any(isinstance(h, session._QueueHandler) for h in logging.getLogger("ck3chronicle").handlers)


def test_a_build_job_can_be_cancelled(tmp_path, monkeypatch):
    saves = saves_folder(tmp_path)
    rows, _ = session.scan_folder(saves)
    real_build = api.build

    def slow_build(*args, progress=None, **kwargs):
        def slowly(p):
            progress(p)
            time.sleep(0.2)
        return real_build(*args, progress=slowly, **kwargs)

    monkeypatch.setattr(session.api, "build", slow_build)
    job = session.BuildJob(saves, tmp_path / "out", [r.key for r in rows], Config(cache=None)).start()
    job.cancel.set()
    events = drain(job)
    assert events[-1][0] == "cancelled"


def test_a_failed_build_is_a_sentence_not_a_traceback(tmp_path):
    saves = saves_folder(tmp_path)
    job = session.BuildJob(saves, tmp_path / "out", ["no-such-run"], Config(cache=None)).start()
    events = drain(job)
    assert events[-1] == ("failed", f"none of the chosen runs is under {saves}")


# ---------------------------------------------------------------- the entry point


def test_smoke_builds_without_a_window(tmp_path, monkeypatch):
    pytest.importorskip("tkinter")
    monkeypatch.setattr(paths, "cache_dir", lambda **kw: tmp_path / "appcache")
    monkeypatch.setattr(paths, "config_path", lambda **kw: tmp_path / "none.toml")
    try:
        import tkinter

        tkinter.Tk().destroy()
    except tkinter.TclError as exc:
        pytest.skip(f"no display for Tk: {exc}")
    saves = saves_folder(tmp_path)
    assert main(["--smoke", str(saves), str(tmp_path / "out")]) == 0
    assert (tmp_path / "out" / "index.html").is_file()
    assert main(["--smoke", str(tmp_path / "nope"), str(tmp_path / "out2")]) == 1


# ---------------------------------------------------------------- the window


@pytest.fixture
def root():
    tkinter = pytest.importorskip("tkinter")
    try:
        window = tkinter.Tk()
    except tkinter.TclError as exc:
        pytest.skip(f"no display for Tk: {exc}")
    window.withdraw()
    yield window
    try:
        window.destroy()
    except tkinter.TclError:
        pass


def test_the_window_lists_ticks_builds_and_opens(tmp_path, root, monkeypatch):
    from ck3chronicle.gui import app

    monkeypatch.setattr(paths, "cache_dir", lambda **kw: tmp_path / "appcache")
    monkeypatch.setattr(paths, "config_path", lambda **kw: tmp_path / "none.toml")
    monkeypatch.setattr(paths, "log_path", lambda **kw: tmp_path / "last-build.log")
    monkeypatch.setattr(paths, "settings_path", lambda **kw: tmp_path / "desktop.json")
    opened = []
    monkeypatch.setattr(session.webbrowser, "open", opened.append)

    saves = saves_folder(tmp_path)
    (saves / "ironman.ck3").write_bytes(b"SAV0103 binary")
    settings = session.Settings(saves, tmp_path / "out")
    window = app.App(root, settings)
    assert len(window.tree.get_children()) == 2
    assert "ironman.ck3" in window.notice.cget("text")
    assert str(window.open_button.cget("state")) == "disabled"

    # untick the second playthrough, build the first
    second = window.tree.get_children()[1]
    window.tree.focus(second)
    window.toggle()
    assert window.chosen() == [window.tree.get_children()[0]]
    window.build()
    deadline = time.time() + 60
    while window.job is not None and time.time() < deadline:
        root.update()
        time.sleep(0.02)
    assert window.job is None
    assert window.status.cget("text").startswith("Done: 1 chronicle(s)")
    assert str(window.open_button.cget("state")) == "normal"
    window.open()
    assert opened and opened[0].endswith("/out/index.html")

    # the choice is remembered
    window.close()
    remembered = json.loads((tmp_path / "desktop.json").read_text(encoding="utf-8"))
    assert remembered["unticked"] == [second]


def test_an_empty_folder_says_so_in_the_window(tmp_path, root, monkeypatch):
    from ck3chronicle.gui import app

    monkeypatch.setattr(paths, "settings_path", lambda **kw: tmp_path / "desktop.json")
    (tmp_path / "empty").mkdir()
    window = app.App(root, session.Settings(tmp_path / "empty", tmp_path / "out"))
    assert "no Crusader Kings III saves" in window.notice.cget("text")
    assert str(window.build_button.cget("state")) == "disabled"
