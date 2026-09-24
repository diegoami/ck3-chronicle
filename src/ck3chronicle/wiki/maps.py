"""Realm maps: the subject ruler's realm on the game's own map, one image per save.

Ported as the drawing and the legend the Realm section shows. The command that
renders a run's maps arrives in M7 with the game-version rule (Ck-parser#58):
game files are used only for saves of the same version.

A save holds no geography: its province records carry holdings and winter,
nothing spatial, and a barony's `capital` is its county's (Ck-parser's PLAN.md §16).
The geography is in the game's files, which this reads and never copies:

* ``map_data/provinces.png`` -- one colour per province;
* ``map_data/definition.csv`` -- province id to that colour;
* ``map_data/default.map`` -- which provinces are sea, lake or river;
* ``common/landed_titles`` -- the province each barony sits on.

A barony belongs to its de jure county, and each county is coloured by its
rank in the realm (`ck3chronicle.core.realm`): held by the ruler, through a direct
vassal, or further down. Anything else is outside the realm, or wasteland.

The images are named by the rule the pages link (`ck3chronicle.core.naming.
realm_map_name`), so rendering them into the delivered ``images/`` is all it takes:
the next build copies them in, and the Realm section shows them. Rendered
here, locally, because CI has no game; what is published is a picture, never
the game's map data (owner's decision on Ck-parser#39).

Needs the ``maps`` extra (Pillow, numpy): ``uv sync --extra maps``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..core.realm import realm
from ..core.titles import TitleIndex

#: vassal rank -> colour; then what is not the realm's
PALETTE = {
    0: (122, 30, 30),
    1: (205, 92, 60),
    2: (240, 180, 120),
    "outside": (215, 212, 204),
    "sea": (180, 200, 220),
    "waste": (170, 165, 150),
}
#: what the page's legend says for each colour
LEGEND = (
    (PALETTE[0], "held by the ruler"),
    (PALETTE[1], "held through a direct vassal"),
    (PALETTE[2], "held further down"),
    (PALETTE["outside"], "outside the realm"),
    (PALETTE["waste"], "wasteland"),
    (PALETTE["sea"], "sea and rivers"),
)

#: where Steam installs the game, per platform, the WSL view of Windows included
GAME_DIRS = (
    "C:/Program Files (x86)/Steam/steamapps/common/Crusader Kings III/game",
    "/mnt/c/Program Files (x86)/Steam/steamapps/common/Crusader Kings III/game",
    "~/.steam/steam/steamapps/common/Crusader Kings III/game",
    "~/.local/share/Steam/steamapps/common/Crusader Kings III/game",
    "~/Library/Application Support/Steam/steamapps/common/Crusader Kings III/game",
)

_BARONY = re.compile(r"(?<![\w])(b_[^\s={}#]+)\s*=\s*\{")
_INSIDE = re.compile(r"[{}]|\bprovince\s*=\s*(\d+)")
_COMMENT = re.compile(r"#[^\n]*")


def barony_provinces(text: str) -> dict[str, int]:
    """Barony key -> province, from one landed_titles file.

    Brace-counted, not pattern-matched: a barony can open with a nested block
    (`cultural_names = { ... }`) before its `province`, which a flat pattern
    misses -- `b_pockington` and `b_leeds` did. Only a `province` at the
    barony's own level counts. The game's files carry `#` comments, which a
    save never does, so they are stripped first.
    """
    text = _COMMENT.sub("", text)
    out: dict[str, int] = {}
    for m in _BARONY.finditer(text):
        depth = 1
        for tok in _INSIDE.finditer(text, m.end()):
            if tok.group(0) == "{":
                depth += 1
            elif tok.group(0) == "}":
                depth -= 1
                if depth == 0:
                    break
            elif depth == 1:
                out[m.group(1)] = int(tok.group(1))
                break
    return out


_WATER = re.compile(r"^(sea_zones|lakes|impassable_seas|river_provinces)\s*=\s*(RANGE|LIST)\s*\{([^}]*)\}")


def find_game_dir() -> Path | None:
    """The first Steam install that has the map files, or None."""
    for candidate in GAME_DIRS:
        path = Path(candidate).expanduser()
        if (path / "map_data" / "provinces.png").is_file():
            return path
    return None


@dataclass
class GameMap:
    """What the game's files say about geography, read once per run."""

    root: Path
    colour: dict[int, int]  #: province id -> packed RGB in provinces.png
    water: set[int]
    barony_province: dict[str, int]
    _raster: object = field(default=None, repr=False)

    @classmethod
    def load(cls, root: Path) -> GameMap:
        colour: dict[int, int] = {}
        text = (root / "map_data" / "definition.csv").read_text(encoding="utf-8-sig", errors="replace")
        for line in text.splitlines():
            parts = line.split(";")
            if len(parts) > 3 and parts[0].isdigit() and all(p.strip().isdigit() for p in parts[1:4]):
                colour[int(parts[0])] = (int(parts[1]) << 16) | (int(parts[2]) << 8) | int(parts[3])
        water: set[int] = set()
        text = (root / "map_data" / "default.map").read_text(encoding="utf-8-sig", errors="replace")
        for line in text.splitlines():
            m = _WATER.match(line.strip())
            if m:
                nums = [int(x) for x in m.group(3).split()]
                water |= set(range(nums[0], nums[1] + 1)) if m.group(2) == "RANGE" else set(nums)
        barony_province: dict[str, int] = {}
        for f in sorted((root / "common" / "landed_titles").glob("*.txt")):
            barony_province.update(barony_provinces(f.read_text(encoding="utf-8-sig", errors="replace")))
        return cls(root=root, colour=colour, water=water, barony_province=barony_province)

    def raster(self, scale: int):
        """provinces.png as packed RGB, every `scale`-th pixel, decoded once."""
        np, Image = _imaging()
        if self._raster is None:
            self._raster = np.asarray(Image.open(self.root / "map_data" / "provinces.png").convert("RGB"))
        img = self._raster[::scale, ::scale]
        return (img[..., 0].astype(np.int32) << 16) | (img[..., 1].astype(np.int32) << 8) | img[..., 2]


def _imaging():
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        raise SystemExit("realm maps need the maps extra: uv sync --extra maps") from None
    return np, Image


@dataclass
class Coverage:
    """How much of the save the map could place: reported on every run."""

    baronies: int = 0
    placed: int = 0
    unplaced: list[str] = field(default_factory=list)


def province_classes(game: GameMap, index: TitleIndex, ruler: int) -> tuple[dict[int, object], Coverage]:
    """Each province's colour key, from its barony's de jure county's rank in the realm."""
    counties = {k: t.depth for k, t in realm(index, ruler).of_tier("county").items()}
    out: dict[int, object] = {}
    cover = Coverage()
    for record in index.by_idx.values():
        if record.tier != "barony":
            continue
        cover.baronies += 1
        province = game.barony_province.get(record.key)
        if province is None:
            cover.unplaced.append(record.key)
            continue
        cover.placed += 1
        county = index.resolve(record.de_jure_liege)
        rank = counties.get(county.key) if county is not None and county.tier == "county" else None
        out[province] = "outside" if rank is None else min(rank, 2)
    return out, cover


def render(game: GameMap, classes: dict[int, object], scale: int = 4, crop: bool = True, margin: int = 40):
    """The map as a PIL image, cropped to the realm with a margin unless told not to."""
    np, Image = _imaging()
    keys = game.raster(scale)
    by_colour = {game.colour[p]: PALETTE[c] for p, c in classes.items() if p in game.colour}
    sea = {game.colour[p] for p in game.water if p in game.colour}
    uniq, inverse = np.unique(keys, return_inverse=True)
    table = np.array(
        [by_colour.get(int(k), PALETTE["sea"] if int(k) in sea else PALETTE["waste"]) for k in uniq],
        dtype=np.uint8,
    )
    rgb = table[inverse.reshape(keys.shape)]
    if crop:
        realm_colours = {PALETTE[0], PALETTE[1], PALETTE[2]}
        inside = np.array([tuple(row) in realm_colours for row in table])[inverse.reshape(keys.shape)]
        ys, xs = np.nonzero(inside)
        if len(ys):
            y0, y1 = max(int(ys.min()) - margin, 0), int(ys.max()) + margin + 1
            x0, x1 = max(int(xs.min()) - margin, 0), int(xs.max()) + margin + 1
            rgb = rgb[y0:y1, x0:x1]
    return Image.fromarray(np.ascontiguousarray(rgb))
