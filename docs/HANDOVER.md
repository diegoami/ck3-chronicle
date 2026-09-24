# Handover

State of ck3-chronicle, kept current PR by PR, written so a fresh session can
continue without the conversation history.

## Where things are

| what | where |
|---|---|
| rules, scope, process | `CLAUDE.md` |
| the plan: decisions, layout, porting map, parity, milestones | `docs/PLAN.md` |
| milestones | issues #1–#7, label `milestone` |
| the reference (read-only) | diegoami/Ck-parser, cloned to `../ck-parser-reference` (not `../Ck-parser`: another session works there) |
| the saves | ck_wiki's Releases, via Ck-parser's `scripts/fetch_saves.sh` |
| the published wiki (the POC's) | diegoami/ck_wiki |

## State

- **M1, the skeleton** (#1): `src/ck3chronicle/` with empty `core/` and `wiki/`,
  a CLI that only answers `--version`, `pyproject.toml` (hatchling, no runtime
  dependencies, extra `maps`, dev group), `uv.lock`, CI on Linux + Windows +
  a non-UTF-8 locale, a wheel check, and a release workflow for PyPI trusted
  publishing. The version is `0.1.0.dev0`; M4 makes it `0.1.0`.
- **PyPI trusted publishing is not connected yet.** Only the owner can: on
  PyPI, a pending publisher for project `ck3-chronicle`, owner `diegoami`,
  repository `ck3-chronicle`, workflow `release.yml`, environment `pypi`
  (and the `pypi` environment on GitHub, optionally with a required reviewer).
  Until then a published release fails at the upload step and uploads nothing.
- **The parity reference** (`docs/PLAN.md` §5) is not tagged yet. The POC session
  tags `poc-reference-1` on Ck-parser once its realm-map PR (Ck-parser#50) is
  merged, and attaches `site-sha256.txt`. Until then, M3's comparison is
  against a local build of Ck-parser's `main`, stating the commit used.

## Next

**M2 (#2): the core ported, free of Neo4j.** Then M3 (#3).

## Done

- 2026-09-24: repository created, with the plan, the rules and milestone issues.
- 2026-09-24: M1, the skeleton (#1).
