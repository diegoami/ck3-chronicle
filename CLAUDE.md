# ck3-chronicle — notes for coding agents

Chronicles of Crusader Kings III playthroughs: a directory of save games in, a
static wiki out. One library, a CLI, a GitHub edition (scaffolded for anyone)
and a desktop edition (Tk). This repository is **the product**. It is being
built from a proof of concept that stays in its own repository as the
reference (below).

Read `docs/HANDOVER.md` first (state, next milestone), then the part of
`docs/PLAN.md` your milestone needs, found through its `##` headings.

## Scope: this repository only

- **Work only in this repository** (`diegoami/ck3-chronicle`). Branches, commits,
  pushes, pull requests and issues happen here and nowhere else.
- **`diegoami/Ck-parser` is the reference, read-only.** It is the proof of
  concept: every behaviour, rule and figure here comes from it. Clone it
  next to this checkout and **never commit, push, branch, comment or open issues
  there**:

  ```
  git clone https://github.com/diegoami/Ck-parser ../Ck-parser
  ```

  Read its `CLAUDE.md` (the rules), `docs/PLAN.md` (the verified facts about the
  save format: §5, §9–§16) and `src/`. Port code from it, don't redesign what it
  already settled. Where it and this file disagree about the product, this file
  wins; where they disagree about the save format, the POC's verified facts win,
  and the disagreement is a finding to report.
- **`diegoami/ck_wiki`** publishes the owner's wiki and holds the saves on its
  Releases. Read it for how the GitHub edition works today (`pages.yml`,
  `README.md`), and **never write to it** unless the milestone says so (M4) and
  the owner has said go.
- **`diegoami/ck_portrait_generator`** is the companion that harvests portraits.
  Plain data files only, no code dependency either way. Read its
  `docs/DECISIONS.md` before assuming anything about portraits.

## Commands

Fill this in as the milestones land; keep it to what works today.

```
uv sync --group dev              # install
uv run pytest -q                 # the suite
```

## Process

Implement on a branch, open a PR that references its milestone issue, and let
the owner merge. A change that needs a decision first is written up on its
issue (the problem, findings with `file:line`, options, a recommended default)
before any code. Owner decisions go to the owner with a recommended default,
never into the code.

### Independent review

Claude does the work itself and does not spawn its own reviewer. At each
milestone it gives the owner a prompt for an **independent reviewer**: a
different model family, in a tool the owner picks (OpenCode with the owner's
Zen key, Codex, …), in a fresh session every time. The review is **offered,
never waited on**, unless the owner says to wait.

| Milestone | Thread | Offer the prompt |
|---|---|---|
| Design written | the milestone issue | with the design |
| PR implementing a milestone, gates green | the PR | when the PR is ready to merge |

Every milestone PR body carries a `Review:` line kept current: `not run`,
`AGREE at <sha>`, or `BLOCK at <sha>: #n, #m`. The reviewer posts one issue per
reproduced finding (labelled `review` plus a category) and always one verdict
comment. When the owner says the review is in: read it from GitHub, **reproduce
each finding before acting**, then fix it (`Fixes #n`) or rebut it with evidence
on the issue. The `review-handoff` skill holds the prompt template.

## Rules

### Working with saves

- Saves are large (~73 MB each, a ~280 MB gamestate, 14 M lines). **Never open
  one with Read, `cat`, `less` or an unbounded `grep`.** Ask questions through the
  parser and print a count or a few fields. A raw look is `grep -m 5 … | cut -c 1-200`.
- Commands over real saves take minutes: redirect output to a log file and read
  its tail.
- Never commit `.ck3` files, an extracted `gamestate`, or generated pages.
- The real saves live on **ck_wiki's Releases**. The POC's
  `scripts/fetch_saves.sh` downloads and checksums them (`SAVES_REPO` overrides).
  They carry the player's account name: treat them as personal data.
- Text I/O is always explicit UTF-8, and `os.devnull`, never `/dev/null`. CI
  runs on Linux **and Windows**; the desktop edition's users are on Windows.

### The format (settled by the POC; see its PLAN.md before changing any)

- The parser is brace-driven, never indentation-driven. Title entries sit at
  column 0. A quoted string can span lines (~1 090 per Germania save); a `#`
  comment or an unclosed string is a `FormatError`, never parsed around. The
  game's own files do carry `#` comments; the save's tokenizer must not accept
  them.
- Everything that touches a real gamestate streams it. Never read a whole
  section into memory.
- `Block` subclasses `list`: test for `Block` first in any isinstance chain.
- Title liege fields are numeric indices into `landed_titles`, resolved
  through the title index, never keys.
- A save has **no vassalage history**: it says who a title's liege *is*. A change
  is only known between two snapshots and is shown as bounds ("between X and
  Y"), never a date. A title absent from a save was destroyed or pruned, and
  the save does not say which: absence is never independence, never an ending.
- A title's history comes from every snapshot that has it, in the lineage or
  not. `current` means open in the newest snapshot; anything older is "held when
  last seen". A reign ends at its holder's death; nobody is guessed into the gap.
- A realm exists per snapshot only. **Depth is vassal rank, counted in holders**,
  never title-tree depth. A title the ruler holds is rank 0 however reached.
- Parentage is stored downward only (`child` lists); parents come from inverting
  every child list, the one expensive pass. `family_data` repeats `spouse` as a
  key while `child` is a list: read with `getall`, never `get`.
- Character names are localization keys with an underscore marking a diacritic:
  drop the marker, never guess the letter. Culture and faith names are keys or
  text depending on the record; transcribe a key, never show the two alike.
- A character is harvestable (gets a portrait slot) only if in `living` **and**
  without `dead_data`.
- Runs are grouped by the save's own fingerprint (seed, bookmark, rules, DLC),
  never by where the save came from. One chronicle per run.
- A save's top-level key set varies even within one run: never assume a section.

### The wiki's contracts

- Image names are **derived**, never assigned, in one module; the companion
  derives the same ones. Changing the rule renames every image: a contract change.
- A page links an image whether or not it exists yet: dropping the file in is
  all it takes, with nothing rebuilt.
- A coat of arms is named after a digest of its **recipe**, never its
  `coat_of_arms_id` (an index inside one save). A recipe keeps repeated keys in
  order: never a dict, never sorted.
- `portraits.json` is **the one harvest queue**, written by the model that
  renders the pages. Never write character names into it.
- The chronicle's reach: title-holders, their direct line (parents, spouses,
  children, siblings), and one ring further only where it holds a title.
- Prose is written from a page's fact sheet only, stored with the sheet's
  digest, shown only while the digest matches; a number the sheet lacks gets the
  paragraph rejected. No LLM SDK: plain HTTP.
- A digest (cache) is never a format: bump its schema when the row shape
  changes, and any failure to read one falls back to the save.

### The product's own rules

- The library **never imports** Neo4j, the GUI, or any edition. Editions depend
  on the library, never the reverse; the graph is a separate add-on, later.
- Nothing owner-specific is hard-wired: repository URLs, the companion's links,
  the user agent, where saves come from. They are configuration (`ck3chronicle.toml`).
- **Parity with the POC is the acceptance test** for porting (M2–M4): on the five
  release saves the site is byte-identical to the POC reference, apart from
  configured URLs (see `docs/PLAN.md`, *Parity*).
