"""The image manifest the companion project scans.

The wiki links every portrait and coat of arms by a name both projects derive
from the save's file name (:mod:`ck3chronicle.core.naming`), so a page is written the
same way whether the image exists yet or not. This file is the other half of
that: a machine-readable list of every image the wiki wants, saying which are
still missing, so the companion (`ck_portrait_generator`) can find its work without
parsing HTML.

The companion keeps its own map from save file to checksum; this repeats the
map in ``saves`` so the two can be checked against each other, and gives every
wanted image the `save` it must be captured from. Uploading is a matter of
dropping files into the chronicle's ``portraits/`` directory under the names
given here — nothing needs regenerating, the links already point at them.

Names are never written, here as in the hand-off: the companion drops them on
principle (Ck-parser's PLAN.md §7).
"""

from __future__ import annotations

import json
from pathlib import Path

from ..core.naming import IMAGE_DIR

from .model import Wiki
from .site import DEFAULT_SITE, Site

#: Bumped when the shape changes in a way a consumer has to notice.
#:
#: 2: an arms `file` is named after the coat of arms' recipe rather than the
#:    save and id, so the same key means a different thing; `definition` added.
#:    Portrait names are unchanged.
#: 3: this is now **the** queue, the hand-off CSVs retiring (Ck-parser#27). A portrait
#:    carries `role` (why the character has a page, so the harvest can take
#:    rulers first), `sex` and `birth`. Nothing earlier changed meaning.
SCHEMA = "ck3-images/3"

#: The manifest's name, in each chronicle and at the root.
MANIFEST = "portraits.json"

# Where the naming rule is written down is carried in every manifest, as
# `docs` (:attr:`ck3chronicle.wiki.site.Site.docs`, configured).
#
# A consumer that has the queue but not the rule can still deliver the wrong
# file name, and the rule is the one thing both projects must agree on without
# talking to each other. So the manifest says where it is written rather than
# assuming whoever reads it already knows.


def wanted_images(wiki: Wiki, have: set[str]) -> list[dict]:
    """Every image the wiki links, portraits first, each flagged with `have`."""
    out: list[dict] = []
    for portrait in wiki.wanted_portraits:
        character = wiki.characters[portrait.character]
        out.append(
            {
                "file": portrait.file,
                "kind": "portrait",
                "save": portrait.save,
                "checksum": portrait.checksum,
                "save_date": portrait.save_date,
                "character": portrait.character,
                "role": character.role,
                "sex": "female" if character.female else "male",
                "birth": character.birth,
                "house": character.house,
                "page": f"characters/{portrait.character}.html",
                "have": portrait.file in have,
            }
        )
    seen: dict[str, dict] = {}
    for arms in wiki.wanted_arms:
        # the same picture is one image, whoever bears it: a title and the house
        # holding it usually share their arms, and two houses can as well
        if arms.file in seen:
            seen[arms.file]["borne_by"].append(arms.page)
            continue
        entry = {
            "file": arms.file,
            "kind": "arms",
            "save": arms.save,
            "checksum": arms.checksum,
            "coat_of_arms_id": arms.coat_of_arms_id,
            "page": arms.page,
            "borne_by": [arms.page],
            "have": arms.file in have,
            # the recipe the game draws from, so this need not be captured
            # in-game at all: pattern, colours and emblem textures
            "definition": arms.definition,
        }
        if arms.title:
            entry["title"] = arms.title
        else:
            entry["house"] = arms.house
        seen[arms.file] = entry
        out.append(entry)
    return out


def with_releases(saves: list[dict], releases: dict[str, str] | None) -> list[dict]:
    """Tag each save with the release it was published in, when that is known.

    A release is a **batch**, not a run. One run already spans three of them
    (0.0.2, 0.0.3 and 0.0.4 each hold one Germania save), so this is here to say
    where a save came from and where its harvested images belong, never to
    decide which chronicle it joins — the fingerprint does that (Ck-parser's PLAN.md §3).
    """
    if not releases:
        return saves
    return [{**save, "release": releases.get(save["file"], "")} for save in saves]


def chronicle_manifest(
    wiki: Wiki, slug: str, have: set[str], releases: dict[str, str] | None = None,
    site: Site = DEFAULT_SITE,
) -> dict:
    images = wanted_images(wiki, have)
    return {
        "schema": SCHEMA,
        "docs": dict(site.docs),
        "chronicle": slug,
        "run_id": wiki.run_id,
        "title": wiki.title_key,
        "images": IMAGE_DIR,
        "saves": with_releases(wiki.saves, releases),
        "wanted": len(images),
        "missing": sum(1 for image in images if not image["have"]),
        "portraits": images,
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def write_chronicle_manifest(
    out: Path, wiki: Wiki, slug: str, have: set[str], releases: dict[str, str] | None = None,
    site: Site = DEFAULT_SITE,
) -> dict:
    """Write ``<chronicle>/portraits.json`` and return what the root needs of it."""
    payload = chronicle_manifest(wiki, slug, have, releases, site)
    write_json(out / MANIFEST, payload)
    return {
        "slug": slug,
        "manifest": f"{slug}/{MANIFEST}",
        "wanted": payload["wanted"],
        "missing": payload["missing"],
        # the batches this chronicle's saves arrived in; a run may span several
        "releases": sorted({s["release"] for s in payload["saves"] if s.get("release")}),
    }


def write_root_manifest(out: Path, chronicles: list[dict], site: Site = DEFAULT_SITE) -> None:
    """One entry point above the chronicles, so a scan starts from a single URL."""
    write_json(
        out / MANIFEST,
        {
            "schema": SCHEMA,
            "docs": dict(site.docs),
            "chronicles": chronicles,
            "wanted": sum(c["wanted"] for c in chronicles),
            "missing": sum(c["missing"] for c in chronicles),
        },
    )
