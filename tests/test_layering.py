"""The package's dependency direction (docs/PLAN.md §3), checked on the source.

``core`` imports nothing else in the package, ``wiki`` imports ``core``, the
editions import both, nothing imports an edition, and nothing imports Neo4j.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

PACKAGE = "ck3chronicle"
SRC = Path(__file__).resolve().parents[1] / "src" / PACKAGE

#: The editions: nothing outside them may import them.
EDITIONS = ("cli", "gui", "scaffold", "__main__")

#: Where each part of the library may reach inside the package.
ALLOWED = {
    "core": ("core",),
    "wiki": ("core", "wiki"),
}


def module_name(path: Path) -> str:
    parts = list(path.relative_to(SRC.parent).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imports(path: Path) -> set[str]:
    """Every module ``path`` imports, relative imports resolved."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    here = module_name(path).split(".")
    if path.name != "__init__.py":
        here.pop()  # a module's relative imports start from its package
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = here[: len(here) - node.level + 1]
                target = ".".join(base + ([node.module] if node.module else []))
                if node.module is None:
                    found.update(f"{target}.{alias.name}" for alias in node.names)
                    continue
            else:
                target = node.module or ""
            found.add(target)
            # `from ck3chronicle import core` imports the subpackage
            if target == PACKAGE:
                found.update(f"{target}.{alias.name}" for alias in node.names)
    return found


SOURCES = sorted(SRC.rglob("*.py"))


def part(module: str) -> str | None:
    """The top-level part of the package a module belongs to, if any."""
    pieces = module.split(".")
    if pieces[0] != PACKAGE:
        return None
    return pieces[1] if len(pieces) > 1 else ""


def test_there_is_source_to_check():
    assert SRC.is_dir() and SOURCES


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: module_name(p))
def test_nothing_imports_neo4j(path):
    assert not any(m.split(".")[0] == "neo4j" for m in imports(path))


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: module_name(p))
def test_dependency_direction(path):
    own = part(module_name(path))
    reached = {part(m) for m in imports(path)} - {None, ""}
    if own in ALLOWED:
        assert reached <= set(ALLOWED[own]), f"{own} reaches {sorted(reached - set(ALLOWED[own]))}"
    if own not in EDITIONS:
        assert not reached & set(EDITIONS), f"{own or PACKAGE} imports an edition"


def test_the_checker_resolves_relative_imports(tmp_path, monkeypatch):
    pkg = tmp_path / PACKAGE / "core"
    pkg.mkdir(parents=True)
    mod = pkg / "x.py"
    mod.write_text("from . import parser\nfrom ..wiki import model\nimport neo4j\n", encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "SRC", tmp_path / PACKAGE)
    assert imports(mod) == {f"{PACKAGE}.core.parser", f"{PACKAGE}.wiki", "neo4j"}
