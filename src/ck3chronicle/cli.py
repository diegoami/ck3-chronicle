"""The ``ck3chronicle`` command. Its subcommands arrive with the milestones."""

from __future__ import annotations

import argparse

from ck3chronicle import __version__


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ck3chronicle",
        description="Chronicles of Crusader Kings III playthroughs: save games in, a static wiki out.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    parser().parse_args(argv)
    return 0
