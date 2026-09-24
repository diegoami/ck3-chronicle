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

## Use

```
pip install git+https://github.com/diegoami/ck3-chronicle
ck3chronicle build <saves> <out>
```

`<saves>` is a folder of `.ck3` files, or one save. Each playthrough in it
becomes a chronicle under `<out>/`, and `<out>/index.html` lists them. Saves
from the same playthrough are grouped by what the saves themselves record,
whatever their file names. A first build reads every character in every save
and takes minutes. Later builds reuse a cache in `./.ck3cache` and take
seconds per save.

Settings live in an optional `ck3chronicle.toml`: the links your site shows,
each chronicle's subject title, who gets a page, where delivered images are.
See [`src/ck3chronicle/config.py`](src/ck3chronicle/config.py). Other
commands: `ck3chronicle fetch` downloads the saves attached to a repository's
Releases, `ck3chronicle queue` works the image queue, and `ck3chronicle prose`
writes paragraphs from each page's facts. Images and the queue are described
in [`docs/IMAGES.md`](docs/IMAGES.md).

From Python:

```python
from ck3chronicle import api
from ck3chronicle.config import load

result = api.build("saves", "site", load(), progress=lambda p: print(p.step, p.steps, p.message))
```

## Planned

- **PyPI:** `pip install ck3-chronicle`.
- **GitHub edition:** `ck3chronicle init github` scaffolds a repository whose
  workflow builds and publishes your wiki from saves uploaded to its Releases.
  Public by default: on GitHub's free plan a published site, and the saves it is
  built from, are public. A private mode builds a downloadable site instead.
- **Desktop edition (Windows):** pick your save folder and an output folder,
  build, open.

MIT licensed. Not affiliated with Paradox Interactive.
