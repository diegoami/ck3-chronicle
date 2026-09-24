"""The ``ck3chronicle`` command.

    ck3chronicle build SAVES OUT            # the wiki: one chronicle per playthrough
    ck3chronicle fetch [DEST]               # the saves on a repository's Releases
    ck3chronicle queue ids|collect ...      # the harvest queue, for the companion
    ck3chronicle prose SAVES                # paragraphs for the rulers' pages

Settings come from ``ck3chronicle.toml`` (``--config``, else the working
directory's, else the defaults); a flag overrides the file. Reports go to
stderr through logging; ``-q`` keeps only warnings.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace
from pathlib import Path

from . import __version__
from .api import BuildError, build, write_prose
from .config import Config, ConfigError, load
from .fetch import FetchError, fetch_saves
from .wiki.model import ROLES
from .wiki.queue import collect, load_entries, write_ids

logger = logging.getLogger("ck3chronicle")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ck3chronicle",
        description="Chronicles of Crusader Kings III playthroughs: save games in, a static wiki out.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--config", type=Path, help="settings file (default: ./ck3chronicle.toml if there is one)")
    p.add_argument("-q", "--quiet", action="store_true", help="report warnings and errors only")
    sub = p.add_subparsers(dest="command", metavar="COMMAND")

    b = sub.add_parser("build", help="build the wiki from a directory of saves")
    b.add_argument("saves", help="a .ck3 file, or a directory of saves holding one or more runs")
    b.add_argument("out", help="output directory")
    b.add_argument("--title", help="subject title for every chronicle (default: the played character's)")
    b.add_argument("--run", dest="run_id", help="build only this run (its id or slug)")
    b.add_argument("--images", type=Path, help="directory of delivered portraits, arms and maps")
    b.add_argument(
        "--prose", type=Path,
        help="directory written by `ck3chronicle prose`; a page shows its paragraph only"
             " while the page still has the facts it was written from",
    )
    b.add_argument(
        "--cache", type=Path,
        help="directory of per-save character digests (default: ./.ck3cache). A save"
             " already digested is read in seconds instead of parsed in minutes",
    )
    b.add_argument("--no-cache", action="store_true", help="read every save from scratch, caching nothing")
    _reach_flags(b)

    f = sub.add_parser("fetch", help="download the saves on a repository's GitHub Releases")
    f.add_argument("dest", nargs="?", default="saves", help="where the saves go (default: ./saves)")
    f.add_argument("--repo", help="owner/name (default: [saves] repository)")

    q = sub.add_parser("queue", help="the harvest queue, from the companion's side")
    qsub = q.add_subparsers(dest="queue_command", required=True)
    ids = qsub.add_parser("ids", help="write one --ids-file per save, rulers first")
    ids.add_argument("manifest", type=Path, help="a chronicle's portraits.json, or the root one")
    ids.add_argument("--out", type=Path, default=Path("ids"))
    ids.add_argument("--role", action="append", choices=ROLES,
                     help="only these roles; repeatable (default: all)")
    ids.add_argument("--all", action="store_true", help="include portraits already harvested")
    col = qsub.add_parser("collect", help="copy harvested captures to the names the wiki links")
    col.add_argument("manifest", type=Path)
    col.add_argument("--from", dest="source", type=Path, required=True,
                     help="the harvester's output directory")
    col.add_argument("--to", dest="target", type=Path, required=True,
                     help="where the wiki looks for delivered images")

    pr = sub.add_parser("prose", help="write paragraphs for the rulers' pages from their facts")
    pr.add_argument("saves", help="a .ck3 file, or a directory of saves")
    pr.add_argument("--out", type=Path, help="prose directory (default: [prose] dir, else ./prose)")
    pr.add_argument("--run", dest="run_id", help="only this run (its id or slug)")
    pr.add_argument("--title", help="subject title (default: each run's own, as the build does)")
    pr.add_argument("--character", action="append", default=[], metavar="ID",
                    help="write this character's page instead of the rulers'; repeatable")
    pr.add_argument("--backend", choices=("template", "openai"),
                    help="default: $CK3_PROSE_BACKEND, else [prose] backend, else template")
    pr.add_argument("--url", help="OpenAI-compatible base URL (default: $CK3_PROSE_URL, else [prose] url)")
    pr.add_argument("--model", help="model name, as the server knows it (default: $CK3_PROSE_MODEL, else [prose] model)")
    pr.add_argument("--force", action="store_true", help="rewrite prose that is still current")
    pr.add_argument("--cache", type=Path, help="character digests, as for the build")
    return p


def _reach_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--no-vassals", action="store_true", help="the title alone, without its vassals")
    p.add_argument(
        "--no-kin", action="store_true",
        help="do not give the direct line pages of their own; parents, spouses and"
             " children are then named on the pages they appear on and nothing more",
    )
    p.add_argument(
        "--no-siblings", action="store_true",
        help="do not give siblings pages of their own; they are then named on the"
             " pages they appear on and nothing more",
    )
    p.add_argument(
        "--no-titled-kin", action="store_true",
        help="stop at the direct line; otherwise its own relatives get pages too,"
             " but only those who hold a title themselves",
    )
    p.add_argument(
        "--no-family", action="store_true",
        help="skip family; parents exist only as other people's child lists, so"
             " finding them costs a full pass over every character in every save",
    )


def _build_config(config: Config, args: argparse.Namespace) -> Config:
    reach = config.reach
    reach = replace(
        reach,
        vassals=reach.vassals and not args.no_vassals,
        kin=reach.kin and not args.no_kin,
        siblings=reach.siblings and not args.no_siblings,
        titled_kin=reach.titled_kin and not args.no_titled_kin,
        family=reach.family and not args.no_family,
    )
    changes: dict = {"reach": reach}
    if args.title:
        changes.update(title=args.title, titles={})
    if args.images:
        changes["images"] = args.images
    if args.prose:
        changes["prose"] = replace(config.prose, dir=args.prose)
    if args.no_cache:
        changes["cache"] = None
    elif args.cache:
        changes["cache"] = args.cache
    return replace(config, **changes)


def _prose_config(config: Config, args: argparse.Namespace) -> Config:
    import os

    env = os.environ
    prose = replace(
        config.prose,
        backend=args.backend or env.get("CK3_PROSE_BACKEND") or config.prose.backend,
        url=args.url or env.get("CK3_PROSE_URL") or config.prose.url,
        model=args.model or env.get("CK3_PROSE_MODEL") or config.prose.model,
    )
    changes: dict = {"prose": prose}
    if args.title:
        changes.update(title=args.title, titles={})
    if args.cache:
        changes["cache"] = args.cache
    return replace(config, **changes)


class _StderrHandler(logging.StreamHandler):
    """Writes to whatever ``sys.stderr`` is now, not what it was when set up."""

    def __init__(self):
        super().__init__()

    @property
    def stream(self):
        return sys.stderr

    @stream.setter
    def stream(self, value):
        pass


def _setup_logging(quiet: bool) -> None:
    if not any(isinstance(h, _StderrHandler) for h in logger.handlers):
        handler = _StderrHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.propagate = False
    logger.setLevel(logging.WARNING if quiet else logging.INFO)


def main(argv: list[str] | None = None) -> int:
    p = parser()
    args = p.parse_args(argv)
    if args.command is None:
        p.print_help(sys.stderr)
        return 2
    _setup_logging(args.quiet)
    try:
        config = load(args.config)
    except ConfigError as exc:
        print(f"ck3chronicle: {exc}", file=sys.stderr)
        return 2

    if args.command == "build":
        try:
            build(args.saves, args.out, _build_config(config, args), run_id=args.run_id)
        except BuildError as exc:
            print(exc, file=sys.stderr)
            return 2
        return 0

    if args.command == "fetch":
        repository = args.repo or config.saves_repository
        if not repository:
            print("ck3chronicle fetch: name the repository with --repo or [saves] repository", file=sys.stderr)
            return 2
        try:
            fetch_saves(repository, args.dest)
        except FetchError as exc:
            print(exc, file=sys.stderr)
            return 2
        return 0

    if args.command == "queue":
        try:
            entries = load_entries(args.manifest)
        except (OSError, ValueError, KeyError) as exc:
            print(f"cannot read {args.manifest}: {exc}", file=sys.stderr)
            return 2
        if args.queue_command == "ids":
            written = write_ids(entries, args.out, set(args.role or ()), args.all)
            for name, n in written.items():
                logger.info("  %s: %d id(s)", name, n)
            logger.info("%d id(s) in %d file(s) under %s/", sum(written.values()), len(written), args.out)
        else:
            counts = collect(entries, args.source, args.target)
            logger.info(", ".join(f"{n} {what}" for what, n in counts.items()))
        return 0

    # prose
    try:
        return write_prose(
            args.saves, args.out, _prose_config(config, args), run_id=args.run_id,
            characters=args.character, force=args.force,
        )
    except (ValueError, BuildError) as exc:
        print(exc, file=sys.stderr)
        return 2
