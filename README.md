# ck3-chronicle

**Chronicles of Crusader Kings III playthroughs.** Point it at a folder of save
games and it writes a static wiki: one chronicle per playthrough, with its titles
and successions, rulers and their families, houses and coats of arms, cultures
and faiths, and the realm, save by save.

> **Status: being built.** This is the product; the working proof of concept is
> [diegoami/Ck-parser](https://github.com/diegoami/Ck-parser), and a wiki built
> by it is published at [diegoami/ck_wiki](https://github.com/diegoami/ck_wiki).
> The plan is in [`docs/PLAN.md`](docs/PLAN.md), the state in
> [`docs/HANDOVER.md`](docs/HANDOVER.md).

## Planned

- **Library and CLI:** `pip install ck3-chronicle`, then
  `ck3chronicle build <saves> <out>`.
- **GitHub edition:** `ck3chronicle init github` scaffolds a repository whose
  workflow builds and publishes your wiki from saves uploaded to its Releases.
  Public by default: on GitHub's free plan a published site, and the saves it is
  built from, are public. A private mode builds a downloadable site instead.
- **Desktop edition (Windows):** pick your save folder and an output folder,
  build, open.

MIT licensed. Not affiliated with Paradox Interactive.
