# Images: the names, the queue, the delivery

A chronicle links a portrait for every character in every save they appear in,
a coat of arms for every house and title that bears one, and a realm map per
save. It links them **whether or not the files exist yet**. Whoever supplies
them (the companion harvester, `ck_portrait_generator`, or anyone else) only
has to deliver files under the right names. Nothing is rebuilt to make a
delivered image appear, apart from the next build copying it in.

This is the contract. `portraits.json` links to it from its `docs` block
(configurable as `[site.docs]` in `ck3chronicle.toml`). It comes from the
proof of concept's `docs/COMPANION_PROPOSAL.md` and is unchanged.

## The rule

Both sides derive the same name from the same facts, and never assign one
(`ck3chronicle.core.naming`):

```python
import hashlib
from pathlib import Path

def save_checksum(save_file: str) -> str:
    return hashlib.sha256(Path(save_file).name.encode("utf-8")).hexdigest()[:12]

def portrait_name(save_file: str, character_id: int) -> str:
    return f"{save_checksum(save_file)}_{character_id}.png"

def arms_name(recipe_digest: str) -> str:
    return f"arms_{recipe_digest}.png"

def realm_map_name(save_file: str, title_key: str) -> str:
    return f"realm_{save_checksum(save_file)}_{title_key}.png"
```

- The save file's **base name** is hashed, not its contents. Either side can
  compute it without opening 70 MB, wherever it keeps the save.
- Keying on the **save**, not the date, gives one portrait per save. The same
  person in three snapshots is three images.
- A `coat_of_arms_id` is an index **inside one save** and never names an
  image. Arms are named after a digest of the **recipe** the game draws them
  from (`ck3chronicle.core.arms`), so the same picture is one file in every
  run. A recipe keeps repeated keys in order.
- Changing any of this renames every image both sides hold. It is a contract
  change, never a refactor.

## The queue: `portraits.json`

A build writes one `portraits.json` in each chronicle and one at the root,
which lists the chronicles. It names every image the chronicle links, the ones
not delivered yet included (schema `ck3-images/3`):

- `saves`: each save's `file`, `checksum` and `date` (and its `release`, when
  the saves were fetched from Releases). This is the checksum map, so a
  consumer can check it against its own.
- `portraits`: one entry per wanted image.
  - `kind: "portrait"` entries carry `file`, `save`, `checksum`, `save_date`,
    `character`, `role` (`ever-holder`, `kin` or `titled-kin`: why they have a
    page, so a harvest can take rulers first), `sex`, `birth`, `house`, `page`
    and `have`.
  - `kind: "arms"` entries carry `file`, `save` and `checksum` (the save the
    recipe was read from), `coat_of_arms_id`, `page`, `borne_by`, `title` or
    `house`, `have`, and `definition`, the recipe itself (pattern, colours,
    emblems), so arms can be drawn without the game.
- `have` is one build's answer, not a promise. The file's absence is the
  truth.
- **Every portrait entry is someone alive in that save**: in `living` and
  without `dead_data`. The game will not render the dead, so asking for them
  is work nobody can do.
- **No character names**, ever. A harvester has no use for them, and the queue
  does not carry them.
- Unknown keys may be added. `schema` changes only when something already
  there changes meaning.

`ck3chronicle queue ids` turns the queue into one id list per save, rulers
first, and `ck3chronicle queue collect` renames a harvester's captures to the
names above.

## Delivery

Put the files, named by the rule, in the images directory (`[images] dir`, or
`ck3chronicle build --images DIR`). The next build copies into each chronicle
the images that chronicle links, and nothing else. Realm maps are drawn from
the game's own files and only for saves of the same game version (M7). They
are delivered the same way and stay out of the queue, since nobody harvests a
map.
