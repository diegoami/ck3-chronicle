"""One snapshot's view of a lineage: the part of the POC's pipeline the wiki uses.

A lineage is a title plus the titles currently held under it (its immediate de
facto vassals). :func:`gather` parses one save into a :class:`SnapshotView`
of it, and :func:`resolve_saves` turns a path into the snapshots of one run,
oldest first. That matters because CK3 prunes dead characters and destroyed
titles as a run goes on, so an old snapshot is the only source for history a
later one has dropped (Ck-parser's PLAN.md §4).

Ported from `ck3parser.pipeline`, cut loose from the graph: loading a lineage
into Neo4j is the graph add-on's, and it builds on these.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from .characters import find_characters, living_characters
from .container import open_gamestate_text
from .digest import CharacterDigest, digest_for
from .family import FamilyIndex, read_index
from .filter import is_filler
from .fingerprint import Fingerprint, fingerprint
from .parser import Block, PushbackLines, iter_children
from .runs import Run, scan
from .titles import TitleIndex, TitleRecord, build_index

CHARACTER_SECTIONS = (("living",), ("dead_unprunable",), ("characters", "dead_prunable"))


@dataclass
class SnapshotView:
    """Everything one snapshot contributes, before it is written or rendered.

    `digest` is where the character questions go when there is one. Asking the
    view rather than the save is what makes a build incremental: the same two
    questions are answered out of a cached digest in seconds, or off the
    gamestate in a minute, and no caller has to know which
    (:mod:`ck3chronicle.core.digest`).
    """

    fp: Fingerprint
    index: TitleIndex
    target: TitleRecord
    vassals: list[TitleRecord]
    characters: dict[int, Block]
    digest: CharacterDigest | None = None

    @property
    def titles(self) -> list[TitleRecord]:
        return [self.target, *self.vassals]

    @property
    def keys(self) -> list[str]:
        return [record.key for record in self.titles]

    def find_characters(self, wanted: set[int]) -> dict[int, Block]:
        if self.digest is not None:
            return self.digest.find(wanted)
        return find_characters(self.fp.file, wanted)

    def family_index(self, wanted: set[int]) -> FamilyIndex:
        if self.digest is not None:
            return self.digest.family_index(wanted)
        return read_index(self.fp.file, wanted)

    def living_characters(self, wanted: set[int]) -> dict[int, Block]:
        """In ``living`` AND carrying no ``dead_data`` -- both, always.

        Someone who died on the save's own date still sits in `living` with the
        block on them, and asking for a portrait of them is work nobody can do
        (Ck-parser's PLAN.md §7).
        """
        if self.digest is not None:
            return self.digest.living(wanted)
        return living_characters(self.fp.file, wanted)


def collect_characters(save_path: str, wanted: set[int]) -> dict[int, Block]:
    """Stream the character sections once each, keeping only the wanted ids."""
    found: dict[int, Block] = {}
    for section in CHARACTER_SECTIONS:
        missing = wanted - found.keys()
        if not missing:
            break
        with open_gamestate_text(save_path) as lines:
            for cid, char in iter_children(PushbackLines(lines), section):
                try:
                    cid_int = int(cid)
                except (TypeError, ValueError):
                    continue
                if cid_int in missing and isinstance(char, Block):
                    found[cid_int] = char
                    missing.discard(cid_int)
                    if not missing:
                        break
    return found


def lineage(index: TitleIndex, title_key: str, with_vassals: bool) -> tuple[TitleRecord, list[TitleRecord]]:
    target = index.get(title_key)
    if target is None:
        raise KeyError(title_key)
    return target, (index.immediate_vassals(target) if with_vassals else [])


def gather(
    save_path: str,
    title_key: str,
    with_vassals: bool = True,
    log=None,
    cache_dir=None,
) -> SnapshotView:
    """Parse one save into the lineage and characters this run needs.

    With a `cache_dir`, the save's characters are read from its digest, or
    digested into it the first time. Everything else is read from the save
    either way: the character sections are where a build's minutes go
    (:mod:`ck3chronicle.core.digest`).
    """
    log = sys.stderr if log is None else log  # not a default: pytest swaps sys.stderr
    fp = fingerprint(save_path, with_sha256=False)
    digest = digest_for(save_path, fp, cache_dir, log)
    index = build_index(save_path)
    for reason, (key, date) in sorted(index.unknown_reasons().items()):
        print(
            f"warning: unknown history type {reason!r} in {Path(save_path).name}, first at"
            f" {key} {date}; it opened a tenure -- if it ends one, add it to titles.TERMINAL_TYPES",
            file=log,
        )
    target, vassals = lineage(index, title_key, with_vassals)
    print(
        f"{Path(save_path).name} [{fp.date}]: {target.key} ({target.display_name}, {target.tier})"
        f" with {len(vassals)} immediate vassal(s)",
        file=log,
    )
    referenced: set[int] = set()
    for record in (target, *vassals):
        referenced |= record.holder_ids()
    chars = digest.find(referenced) if digest else collect_characters(save_path, referenced)
    kept = {cid: char for cid, char in chars.items() if not is_filler(cid, char, referenced)}
    print(
        f"  characters: {len(referenced)} referenced, {len(chars)} found, {len(kept)} kept,"
        f" {len(referenced - chars.keys())} missing",
        file=log,
    )
    return SnapshotView(
        fp=fp, index=index, target=target, vassals=vassals, characters=kept, digest=digest
    )



def resolve_saves(path: str, run_id: str | None = None, log=None) -> list[str]:
    """One save path, or every snapshot of the run in a directory, oldest first."""
    log = sys.stderr if log is None else log
    target = Path(path)
    if target.is_file():
        return [str(target)]
    runs: list[Run] = scan(target, with_sha256=False)
    if not runs:
        raise FileNotFoundError(f"no .ck3 saves under {target}")
    if run_id is not None:
        runs = [r for r in runs if r.run_id == run_id]
        if not runs:
            known = ", ".join(r.run_id for r in scan(target, with_sha256=False)) or "none"
            raise LookupError(f"no run {run_id!r} under {target}; known runs: {known}")
    elif len(runs) > 1:
        names = "\n".join(f"  {r.run_id}  ({len(r.snapshots)} snapshots)" for r in runs)
        raise LookupError(f"{target} holds {len(runs)} runs; pick one with --run\n{names}")
    run = runs[0]
    for warning in run.warnings:
        print(f"warning: {warning}", file=log)
    for note in run.notes:
        print(f"note: {note}", file=log)
    print(f"run {run.run_id}: {len(run.snapshots)} snapshot(s), oldest first", file=log)
    return [snapshot.fp.file for snapshot in run.snapshots]
