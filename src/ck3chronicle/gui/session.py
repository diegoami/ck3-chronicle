"""Everything the window does, without the window.

The Tk layer (:mod:`ck3chronicle.gui.app`) only draws and forwards clicks;
what a click means is here, where a test can drive it: which playthroughs a
folder holds, what the player chose last time, whether an output folder is
safe to write into, and the build itself, on a worker thread, reporting through
a queue the window polls.
"""

from __future__ import annotations

import json
import logging
import queue
import shutil
import threading
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path

from .. import api
from ..config import Config, ConfigError, load
from ..core.runs import Run
from ..wiki.manifest import MANIFEST
from . import paths

logger = logging.getLogger("ck3chronicle")


class FolderProblem(Exception):
    """What is wrong with a folder the player chose, in a sentence for them."""


# ---------------------------------------------------------------- playthroughs


@dataclass(frozen=True)
class Playthrough:
    """One run, as a row of the list: cheap, from the saves' headers only."""

    key: str  #: the run's slug, what a build is asked for
    character: str
    version: str
    saves: int
    years: str

    @classmethod
    def of(cls, run: Run) -> "Playthrough":
        first, newest = run.snapshots[0].fp, run.snapshots[-1].fp
        # a save can lack its date (#19): the list says so rather than fail
        start, end = (fp.date.split(".", 1)[0] if fp.date else "?" for fp in (first, newest))
        return cls(
            key=run.slug,
            character=newest.player_name or "(unknown ruler)",
            version=run.version or "?",
            saves=len(run.snapshots),
            years=start if start == end else f"{start}–{end}",
        )


def scan_folder(folder: str | Path) -> tuple[list[Playthrough], list[tuple[str, str]]]:
    """The playthroughs in `folder`, and the files skipped as unreadable.

    Raises :class:`FolderProblem` with a sentence for the player when there is
    nothing to build.
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise FolderProblem(f"The folder {folder} does not exist.")
    skipped: list[tuple[str, str]] = []
    try:
        runs = api.discover(folder, skipped=skipped)
    except api.BuildError:
        if skipped:
            raise FolderProblem(
                f"None of the {len(skipped)} save file(s) in {folder} can be read."
                " Ironman saves cannot be read, only ordinary ones."
            ) from None
        raise FolderProblem(
            f"There are no Crusader Kings III saves (.ck3 files) in {folder}."
        ) from None
    return [Playthrough.of(run) for run in runs], skipped


# ---------------------------------------------------------------- remembered choices


@dataclass
class Settings:
    saves: Path
    output: Path
    #: playthroughs the player unticked; a new one is ticked by default
    unticked: set[str] = field(default_factory=set)

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path or paths.settings_path()
        settings = cls(paths.default_saves_dir(), paths.default_output_dir())
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return settings  # first run, or unreadable: the defaults, never an error
        if isinstance(data, dict):
            if isinstance(data.get("saves"), str):
                settings.saves = Path(data["saves"])
            if isinstance(data.get("output"), str):
                settings.output = Path(data["output"])
            if isinstance(data.get("unticked"), list):
                settings.unticked = {k for k in data["unticked"] if isinstance(k, str)}
        return settings

    def save(self, path: Path | None = None) -> None:
        path = path or paths.settings_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps({"saves": str(self.saves), "output": str(self.output),
                            "unticked": sorted(self.unticked)}, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass  # remembering is a convenience; failing to is not worth a dialog


def desktop_config(path: Path | None = None) -> Config:
    """The app-data ``ck3chronicle.toml`` if there is one, with the cache in app-data.

    Raises :class:`FolderProblem` when the file exists but cannot be used.
    """
    path = path or paths.config_path()
    try:
        config = load(path) if path.is_file() else Config()
    except ConfigError as exc:
        raise FolderProblem(f"The settings file {path} cannot be used: {exc}") from None
    if config.cache == Path(".ck3cache"):  # the default, relative to wherever the .exe was started
        config = config.with_(cache=paths.cache_dir())
    return config


# ---------------------------------------------------------------- the output folder


def output_warning(out: str | Path) -> str | None:
    """A question to ask before writing into `out`, or None when it is safe.

    Safe: missing, empty, or holding an earlier build (its ``portraits.json``).
    """
    out = Path(out)
    if not out.exists():
        return None
    if not out.is_dir():
        return f"{out} is a file, not a folder."
    if (out / MANIFEST).is_file() or not any(out.iterdir()):
        return None
    return (
        f"{out} already holds other files. The chronicles are written beside them,"
        " and files with the same names are replaced. Build there anyway?"
    )


def has_chronicle(out: str | Path) -> bool:
    return (Path(out) / "index.html").is_file()


def open_chronicle(out: str | Path) -> None:
    webbrowser.open((Path(out).resolve() / "index.html").as_uri())


def cache_size(config: Config) -> int:
    folder = config.cache
    if folder is None or not Path(folder).is_dir():
        return 0
    return sum(p.stat().st_size for p in Path(folder).rglob("*") if p.is_file())


def clear_cache(config: Config) -> None:
    if config.cache is not None and Path(config.cache).is_dir():
        shutil.rmtree(config.cache, ignore_errors=True)


# ---------------------------------------------------------------- the build


class _QueueHandler(logging.Handler):
    def __init__(self, events: queue.Queue):
        super().__init__(logging.INFO)
        self.events = events

    def emit(self, record: logging.LogRecord) -> None:
        self.events.put(("log", record.levelno, record.getMessage()))


class BuildJob:
    """One build on a worker thread, reporting through `events`.

    Events, in order: any number of ``("progress", Progress)`` and ``("log",
    level, text)``, then exactly one of ``("done", Result)``, ``("cancelled",
    message)`` or ``("failed", message)``. Tk is not thread-safe, so the window
    only ever reads the queue, from its own thread.
    """

    def __init__(self, saves: Path, out: Path, keys: list[str], config: Config, log_file: Path | None = None):
        self.saves, self.out, self.keys, self.config = Path(saves), Path(out), list(keys), config
        self.log_file = log_file
        self.events: queue.Queue = queue.Queue()
        self.cancel = threading.Event()
        self.thread = threading.Thread(target=self._run, name="ck3chronicle-build", daemon=True)

    def start(self) -> "BuildJob":
        self.thread.start()
        return self

    @property
    def running(self) -> bool:
        return self.thread.is_alive()

    def _run(self) -> None:
        handlers: list[logging.Handler] = [_QueueHandler(self.events)]
        if self.log_file is not None:
            try:
                self.log_file.parent.mkdir(parents=True, exist_ok=True)
                file_handler = logging.FileHandler(self.log_file, mode="w", encoding="utf-8")
                file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
                handlers.append(file_handler)
            except OSError:
                pass
        previous = logger.level
        logger.setLevel(logging.INFO)
        for handler in handlers:
            logger.addHandler(handler)
        try:
            result = api.build(
                self.saves, self.out, self.config,
                progress=lambda p: self.events.put(("progress", p)),
                run_ids=self.keys, cancel=self.cancel,
            )
            self.events.put(("done", result))
        except api.Cancelled:
            self.events.put(("cancelled", "Stopped. Chronicles finished before the stop are complete."))
        except api.BuildError as exc:
            self.events.put(("failed", str(exc)))
        except Exception as exc:  # anything else: a sentence and where the details are
            logger.exception("the build failed")
            where = f" The details are in {self.log_file}." if self.log_file else ""
            self.events.put(("failed", f"The build failed: {exc}.{where}"))
        finally:
            for handler in handlers:
                logger.removeHandler(handler)
                handler.close()
            logger.setLevel(previous)
