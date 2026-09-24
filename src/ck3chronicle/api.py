"""The library's front door: a directory of saves in, a static wiki out.

    from ck3chronicle import api
    result = api.build("saves", "site", config, progress=print)

Saves are grouped into runs by :mod:`ck3chronicle.core.runs`, and each run
becomes its own chronicle under ``<out>/<seed>-<version>/``, because the seed
and the game version are what tell one playthrough from another. A landing
page at the root lists them, so dropping more saves into the source adds more
chronicles without any configuration.

Each chronicle needs a subject title: the configured one for that run, else
the configured one for every run, else the played character's primary title
in that run's newest save, which is what the playthrough was about.

It reports two ways. `progress` is called with a :class:`Progress` at every
step, for a window's progress bar; everything worth reading goes to the
``ck3chronicle`` logger, warnings as warnings, for a terminal or a log file.
Nothing is printed. Ported from the POC's ``ck3wiki.build`` and
``ck3wiki.prose``'s command.
"""

from __future__ import annotations

import io
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .config import Config
from .core.fingerprint import fingerprint
from .core.player import primary_title_key
from .core.runs import Run, Snapshot, scan
from .core.snapshot import gather
from .wiki.manifest import write_chronicle_manifest, write_root_manifest
from .wiki.model import Wiki, build_wiki
from .wiki.prose import generate, load_prose, make_backend, rulers
from .wiki.render import harvested, write_landing, write_site

logger = logging.getLogger("ck3chronicle")


class BuildError(Exception):
    """Nothing could be built: no saves, no such run, or no chronicle came of it."""


@dataclass(frozen=True)
class Progress:
    """One step of a build.

    `stage` is ``"start"``, ``"read"`` (one save read), ``"write"`` (one
    chronicle written) or ``"done"``; `step` of `steps` counts both reads and
    writes, so ``step / steps`` is how far along the build is.
    """

    stage: str
    message: str
    step: int = 0
    steps: int = 0
    run: str | None = None


ProgressCallback = Callable[[Progress], None]


@dataclass
class Result:
    """What a build wrote: one entry per chronicle, as the landing page lists them."""

    out: Path
    chronicles: list[dict] = field(default_factory=list)

    @property
    def pages(self) -> int:
        return sum(c["pages"] for c in self.chronicles)

    @property
    def images_wanted(self) -> int:
        return sum(c["images"]["wanted"] for c in self.chronicles)

    @property
    def images_missing(self) -> int:
        return sum(c["images"]["missing"] for c in self.chronicles)


class _LogStream(io.TextIOBase):
    """A text stream whose lines go to the logger.

    The core reports on a stream, as the POC's did; this is how its lines
    reach logging instead of stderr. A line starting ``warning:`` is logged as
    a warning.
    """

    def __init__(self, log: logging.Logger):
        self._log = log
        self._pending = ""

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        self._pending += text
        *lines, self._pending = self._pending.split("\n")
        for line in lines:
            self._emit(line)
        return len(text)

    def flush(self) -> None:
        if self._pending:
            self._emit(self._pending)
            self._pending = ""

    def _emit(self, line: str) -> None:
        if line:
            self._log.log(logging.WARNING if line.startswith("warning:") else logging.INFO, line)


# ---------------------------------------------------------------- the steps


def read_releases(save_path: str | Path) -> dict[str, str]:
    """Save file name -> the release it was published in, if the fetch said.

    Optional: a directory of saves someone assembled by hand has no releases,
    and the build says nothing about them rather than guessing.
    """
    path = Path(save_path)
    index = (path if path.is_dir() else path.parent) / "releases.json"
    try:
        loaded = json.loads(index.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in loaded.items() if isinstance(v, str)} if isinstance(loaded, dict) else {}


def discover(save_path: str | Path, run_id: str | None = None) -> list[Run]:
    """The runs to build: every run in a directory, or the one run of a file.

    Raises :class:`BuildError` when there is nothing to build.
    """
    path = Path(save_path)
    if path.is_file():
        fp = fingerprint(path, with_sha256=False)
        return [
            Run(
                run_id=fp.run_id,
                random_seed=fp.random_seed,
                bookmark_date=fp.bookmark_date,
                version=fp.version,
                slug=fp.run_slug,
                snapshots=[Snapshot(fp=fp, mtime=path.stat().st_mtime)],
            )
        ]
    if not path.is_dir():
        raise BuildError(f"no such save or directory: {path}")
    runs = scan(path, with_sha256=False)
    if not runs:
        raise BuildError(f"no .ck3 saves under {path}")
    if run_id is not None:
        runs = [r for r in runs if r.run_id == run_id or r.slug == run_id]
        if not runs:
            raise BuildError(f"no run {run_id!r} under {path}")
    return runs


def subject_of(run: Run, override: str | None, log) -> str | None:
    """Which title this chronicle is about."""
    if override:
        return override
    newest = run.snapshots[-1]
    key = primary_title_key(newest.fp.file, fp=newest.fp)
    if key is None:
        print(f"warning: cannot tell what run {run.slug} is about; configure its title", file=log)
    return key


def load_run(
    run: Run, subject: str, config: Config, log, on_read: Callable[[str], None] | None = None,
) -> Wiki | None:
    """One run's snapshots, merged into the wiki's picture of it.

    The build and the prose writer both start here, so the facts a paragraph
    is written from are the facts the page is built from.
    """
    reach = config.reach
    views = []
    for snapshot in run.snapshots:
        try:
            views.append(
                gather(snapshot.fp.file, subject, reach.vassals, log=log, cache_dir=config.cache)
            )
        except KeyError:
            print(f"warning: {subject!r} is not in {Path(snapshot.fp.file).name}, skipped", file=log)
        if on_read is not None:
            on_read(Path(snapshot.fp.file).name)
    if not views:
        print(f"warning: nothing to build for run {run.slug}", file=log)
        return None
    return build_wiki(
        views, subject, with_family=reach.family, with_kin=reach.kin,
        with_siblings=reach.siblings, with_titled_kin=reach.titled_kin,
    )


def build_one(
    run: Run, subject: str, out: Path, config: Config, log,
    releases: dict[str, str] | None = None, on_read: Callable[[str], None] | None = None,
) -> dict | None:
    wiki = load_run(run, subject, config, log, on_read)
    if wiki is None:
        return None
    prose, stale = load_prose(config.prose.dir, run.slug, wiki)
    if config.prose.dir is not None:
        print(f"  prose: {len(prose)} page(s), {stale} stale and left out", file=log)
    pages = write_site(wiki, out / run.slug, config.images, top=True, prose=prose, site=config.site)
    images = write_chronicle_manifest(
        out / run.slug, wiki, run.slug, harvested(config.images), releases, site=config.site
    )
    root = wiki.root
    print(
        f"  {run.slug}: {pages} pages, {images['missing']} of {images['wanted']}"
        f" images still to harvest",
        file=log,
    )
    return {
        "slug": run.slug,
        # what write_site actually wrote, not a re-derivation: the summary used
        # to add up titles, characters and houses, which silently went wrong the
        # moment cultures and faiths got pages too
        "pages": pages,
        "name": root.name if root else subject,
        "seed": run.random_seed,
        "version": run.version,
        "snapshots": len(wiki.snapshots),
        "titles": len(wiki.titles),
        "characters": len(wiki.characters),
        "houses": len(wiki.houses),
        "images": images,
    }


# ---------------------------------------------------------------- the build


def build(
    saves: str | Path,
    out: str | Path,
    config: Config | None = None,
    progress: ProgressCallback | None = None,
    *,
    run_id: str | None = None,
) -> Result:
    """Build every chronicle the saves hold into `out`.

    `saves` is a directory of saves or one save; `run_id` builds only that run
    (its id or slug). Raises :class:`BuildError` when nothing can be built.
    """
    config = config or Config()
    out = Path(out)
    stream = _LogStream(logger)
    runs = discover(saves, run_id)
    steps = sum(len(run.snapshots) + 1 for run in runs)
    done = 0

    def report(stage: str, message: str, run: str | None = None) -> None:
        if progress is not None:
            progress(Progress(stage, message, done, steps, run))

    releases = read_releases(saves)
    print(f"{len(runs)} run(s) to build", file=stream)
    report("start", f"{len(runs)} run(s) to build")
    result = Result(out=out)
    for run in runs:
        subject = subject_of(run, config.subject_for(run.slug, run.run_id), stream)
        if subject is None:
            done += len(run.snapshots) + 1
            report("write", f"{run.slug}: skipped, no subject", run.slug)
            continue

        def on_read(name: str, slug: str = run.slug) -> None:
            nonlocal done
            done += 1
            report("read", name, slug)

        entry = build_one(run, subject, out, config, stream, releases, on_read)
        done += 1
        if entry is not None:
            result.chronicles.append(entry)
            report("write", f"{run.slug}: {entry['pages']} pages", run.slug)
        else:
            report("write", f"{run.slug}: nothing to build", run.slug)
    stream.flush()

    if not result.chronicles:
        raise BuildError("no chronicles could be built")
    write_landing(out, result.chronicles, site=config.site)
    write_root_manifest(out, [c["images"] for c in result.chronicles], site=config.site)
    logger.info("wrote %d chronicle(s), %d pages, to %s/", len(result.chronicles), result.pages, out)
    logger.info("%d image(s) still to harvest; see %s/portraits.json", result.images_missing, out)
    report("done", f"{len(result.chronicles)} chronicle(s), {result.pages} pages")
    return result


# ---------------------------------------------------------------- prose


def write_prose(
    saves: str | Path,
    out: str | Path | None = None,
    config: Config | None = None,
    *,
    run_id: str | None = None,
    characters: list[str] | None = None,
    force: bool = False,
) -> int:
    """Write prose for each run's rulers (or the given characters) under `out`.

    Returns 0 when every page got current prose, 1 when some were rejected or
    had no page, 2 when the backend could not be asked at all. The API key is
    read from ``CK3_PROSE_API_KEY`` and nowhere else.
    """
    config = config or Config()
    settings = config.prose
    root = Path(out) if out is not None else (settings.dir or Path("prose"))
    backend = make_backend(
        settings.backend, settings.url, settings.model, os.environ.get("CK3_PROSE_API_KEY"),
        user_agent=settings.user_agent,
    )
    runs = discover(saves, run_id)
    stream = _LogStream(logger)
    status = 0
    try:
        for run in runs:
            subject = subject_of(run, config.subject_for(run.slug, run.run_id), stream)
            if subject is None:
                continue
            wiki = load_run(run, subject, config, stream)
            if wiki is None:
                continue
            pages = [("characters", c) for c in characters or ()] or rulers(wiki)
            counts = generate(wiki, run.slug, pages, backend, root, force, stream)
            print(f"  {run.slug}: " + ", ".join(f"{n} {k}" for k, n in counts.items()), file=stream)
            if counts["failed"]:
                return 2
            if counts["rejected"] or counts["missing"]:
                status = 1
        usage = getattr(backend, "usage", None)
        if usage:
            print(f"tokens billed: {usage['prompt_tokens']} in, {usage['completion_tokens']} out", file=stream)
    finally:
        stream.flush()
    return status
