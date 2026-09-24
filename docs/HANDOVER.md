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

- **M1, the skeleton** (#1, merged): `src/ck3chronicle/`, a CLI that only
  answers `--version`, `pyproject.toml` (hatchling, no runtime dependencies,
  extra `maps`, dev group), `uv.lock`, CI on Linux + Windows + a non-UTF-8
  locale, a wheel check, and a release workflow for PyPI trusted publishing.
  The version is `0.1.0.dev0`; M4 makes it `0.1.0`.
- **M2, the core** (#2): `core/` holds the POC's parser-side modules as they
  were at `poc-reference-1`, only their docstrings' references changed
  (module paths; "Ck-parser's PLAN.md §n" and "Ck-parser#n" point at the POC),
  plus `naming` (was `portraits`), `snapshot` (`SnapshotView`,
  `collect_characters`, `lineage`, `gather`, `resolve_saves`, cut loose from
  the graph), `history` (`holder_intervals`) and `population` (`Person`,
  `character_props`, `stream_people`: public, for the graph add-on).
  `core` still reports through a `log` file object, as the POC does; `api`
  turns that into logging.
- **M3, the wiki** (#3): `wiki/` holds the POC's `model`, `render`, `manifest`,
  `queue`, `prose` and `maps` at `poc-reference-1`, plus `site` (the links a
  site carries). `api.build(saves, out, config, progress)` is the POC's
  `ck3wiki.build`, reporting through a `Progress` callback and the
  `ck3chronicle` logger; `config` reads `ck3chronicle.toml`; `fetch` is the
  POC's `scripts/fetch_saves.sh` in Python. The CLI has `build`, `fetch`,
  `queue` and `prose`. **Parity holds**: `scripts/parity.sh` builds the five
  release saves with `scripts/parity.toml` (the POC's own links) and all
  25 133 files match `poc-reference-1`'s `site-sha256.txt`, with no
  normalisation (3 min 31 s cold, 1 min 14 s warm, 1.1 GB peak).
- **Maps have no command yet**: the drawing is ported, the command that renders
  a run's maps comes in M7 with the game-version rule (Ck-parser#58; the rule
  is on #7 and in `docs/PLAN.md` §6, §8).
- **PyPI trusted publishing is not connected yet, and deferred by the owner**
  until they have used the package themselves (M4). Only the owner can: on
  PyPI, a pending publisher for project `ck3-chronicle`, owner `diegoami`,
  repository `ck3-chronicle`, workflow `release.yml`, environment `pypi`
  (and the `pypi` environment on GitHub, optionally with a required reviewer).
  Until then a published release fails at the upload step and uploads nothing.
- **The parity reference**: tag `poc-reference-1` on Ck-parser
  (`40fd399`, also its `main` on 2026-09-24), release assets `site-sha256.txt`,
  `inputs-sha256.txt` and `reference.json`. Built with no flags over the five
  release saves: 3 chronicles, 25 133 files. `reference.json` names the three
  owner-specific URLs; configured with the same values, a port's site should
  match byte for byte with no normalisation.

### POC tests: where each went

| POC test | here |
|---|---|
| `test_{parser,container,cultures,digest,dynasties,family,filter,fingerprint,realm,runs,titles,vassalage}.py` | same names, as they were, imports renamed |
| `test_digest.py::test_a_cached_build_renders_exactly_what_an_uncached_one_does` | ported in M3, through `api.build` |
| `test_pipeline.py` | `test_snapshot.py`: its non-graph parts (`gather`, `lineage`, `collect_characters`, `resolve_saves`), checked on the view instead of through Cypher. Its three checks between snapshots (changed history, changed death date, `--no-check`) go with `consistency`, later; the rest is the graph load, the add-on's |
| `test_graph.py` | `test_history.py` (`holder_intervals`, plus the tenure a later snapshot closes) and `test_population.py` (`stream_people`, `character_props`); the Cypher, config and schema tests stay with the graph add-on |
| `test_handoff.py` | not ported (retired, Ck-parser#27); its two `living_characters` tests are in `test_characters.py` |
| `test_wiki.py`, `test_prose.py`, `test_queue.py` | same names, ported in M3; `helpers.build_main`, `queue_main` and `prose_main` run the POC's argument lists through `ck3chronicle`. `LEAVES_AND_PASSES` and `VANISHES` moved from `test_wiki.py` to `helpers.py` (`test_realm.py` needs them) |
| `test_maps.py` | ported in M3 but for its two command tests, which come with the command in **M7** |
| `test_sections.py` | with `ck3chronicle debug sections` (not scheduled) |
| `test_consistency.py` | with `consistency`, later (a run check) |
| `test_integration_neo4j.py` | the graph add-on |

## Next

**M4 (#4): 0.1.0 on PyPI, and ck_wiki runs on it.** Needs the owner: the
trusted publisher on PyPI, and a go before anything writes to ck_wiki.

**The POC has moved past `poc-reference-1`** (2026-09-24), and the port has
not followed yet:
- Ck-parser#51, a DLC toggled mid-run keeps a playthrough whole: changes
  `core/runs.py`. A small catch-up PR, after M3.
- Ck-parser#53 (the game's own words), #57 (culture aspects) and #59 (game
  files only for the same version): M7.
- Ck-parser#56 ("Culture N" on the 1.3/1.4 saves) would change pages without
  the game's files, so it needs a `poc-reference-2`, and parity moves to it.

## Done

- 2026-09-24: repository created, with the plan, the rules and milestone issues.
- 2026-09-24: M1, the skeleton (#1).
- 2026-09-24: M2, the core ported, free of Neo4j (#2).
- 2026-09-24: M3, the wiki, `build()` and configuration, at parity with `poc-reference-1` (#3).
