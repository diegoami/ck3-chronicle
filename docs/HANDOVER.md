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
  `core` still reports through a `log` file object, as the POC does; M3's
  `build()` turns that into progress callbacks and logging.
- **PyPI trusted publishing is not connected yet.** Only the owner can: on
  PyPI, a pending publisher for project `ck3-chronicle`, owner `diegoami`,
  repository `ck3-chronicle`, workflow `release.yml`, environment `pypi`
  (and the `pypi` environment on GitHub, optionally with a required reviewer).
  Until then a published release fails at the upload step and uploads nothing.
- **The parity reference exists**: tag `poc-reference-1` on Ck-parser
  (`40fd399`, also its `main` on 2026-09-24), release assets `site-sha256.txt`,
  `inputs-sha256.txt` and `reference.json`. Built with no flags over the five
  release saves: 3 chronicles, 25 133 files. `reference.json` names the three
  owner-specific URLs; configured with the same values, a port's site should
  match byte for byte with no normalisation.

### POC tests: where each went

| POC test | here |
|---|---|
| `test_{parser,container,cultures,digest,dynasties,family,filter,fingerprint,realm,runs,titles,vassalage}.py` | same names, as they were, imports renamed |
| `test_digest.py::test_a_cached_build_renders_exactly_what_an_uncached_one_does` | **M3**: it runs the wiki build |
| `test_pipeline.py` | `test_snapshot.py`: its non-graph parts (`gather`, `lineage`, `collect_characters`, `resolve_saves`), checked on the view instead of through Cypher. Its three checks between snapshots (changed history, changed death date, `--no-check`) go with `consistency`, later; the rest is the graph load, the add-on's |
| `test_graph.py` | `test_history.py` (`holder_intervals`, plus the tenure a later snapshot closes) and `test_population.py` (`stream_people`, `character_props`); the Cypher, config and schema tests stay with the graph add-on |
| `test_handoff.py` | not ported (retired, Ck-parser#27); its two `living_characters` tests are in `test_characters.py` |
| `test_wiki.py`, `test_prose.py`, `test_queue.py` | **M3**. `LEAVES_AND_PASSES` and `VANISHES` moved from `test_wiki.py` to `helpers.py` (`test_realm.py` needs them) |
| `test_maps.py` | **M7** (realm maps) |
| `test_sections.py` | with `ck3chronicle debug sections` (not scheduled) |
| `test_consistency.py` | with `consistency`, later (a run check) |
| `test_integration_neo4j.py` | the graph add-on |

## Next

**M3 (#3): the wiki, `build()` and configuration, at parity** with
`poc-reference-1`. Then M4 (#4).

## Done

- 2026-09-24: repository created, with the plan, the rules and milestone issues.
- 2026-09-24: M1, the skeleton (#1).
- 2026-09-24: M2, the core ported, free of Neo4j (#2).
