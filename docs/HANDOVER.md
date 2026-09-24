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

- **Nothing is built yet.** The repository holds the license, this handover,
  the plan, `CLAUDE.md`, the review skill and a SessionStart hook that does
  nothing until `pyproject.toml` exists.
- **The parity reference** (`docs/PLAN.md` §5) is not tagged yet. The POC session
  tags `poc-reference-1` on Ck-parser once its realm-map PR (Ck-parser#50) is
  merged, and attaches `site-sha256.txt`. Until then, M3's comparison is
  against a local build of Ck-parser's `main`, stating the commit used.

## Next

**M1 (#1): the skeleton.** Then M2 (#2), porting the core free of Neo4j.

## Done

- 2026-09-24: repository created, with the plan, the rules and milestone issues.
