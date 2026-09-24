"""Download the saves attached to a repository's GitHub Releases.

    ck3chronicle fetch saves --repo owner/name

Ported from the POC's ``scripts/fetch_saves.sh``. Saves are tens of megabytes
each and never in git, so a checkout or a workflow gets them from Releases.
Every release is read, not a fixed list, so attaching a save from a new
playthrough is all it takes to add a chronicle. A file on more than one
release is fetched once; every download is checked against the SHA-256 the
API reports, and a file already there with the right checksum is kept.

The repository is always named (``[saves] repository`` or ``--repo``), never
inferred from ``GITHUB_REPOSITORY``: that names whichever repository a
workflow runs in, which need not be where the saves are. ``GITHUB_TOKEN``, if
set, authenticates, and is only ever read from the environment.

``releases.json`` records which release each save came from, for the manifest
to pass on. It is written even when empty, so a build can tell "no release
information" from "not fetched". It is where a save came from, never how runs
are grouped: that is the save's own fingerprint (Ck-parser's PLAN.md §7).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import __version__

logger = logging.getLogger("ck3chronicle")

API = "https://api.github.com"
PER_PAGE = 100


class FetchError(RuntimeError):
    """The Releases could not be read, or a download did not check out."""


@dataclass(frozen=True)
class Asset:
    name: str
    sha256: str  #: empty when the API gave no digest
    url: str
    tag: str


def _request(url: str, token: str | None, accept: str) -> urllib.request.Request:
    headers = {"Accept": accept, "User-Agent": f"ck3-chronicle/{__version__}"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url, headers=headers)


Opener = Callable[[urllib.request.Request], object]


def list_assets(repository: str, token: str | None = None, opener: Opener = urllib.request.urlopen) -> list[Asset]:
    """Every ``.ck3`` asset on the repository's published releases, once each.

    Deduplicated by checksum (by name where the API gives none), in the order
    the API lists releases: newest first.
    """
    assets: list[Asset] = []
    seen: set[str] = set()
    page = 1
    while True:
        url = f"{API}/repos/{repository}/releases?per_page={PER_PAGE}&page={page}"
        try:
            with opener(_request(url, token, "application/vnd.github+json")) as response:
                releases = json.load(response)
        except OSError as exc:
            raise FetchError(f"cannot list the releases of {repository}: {exc}") from None
        if not isinstance(releases, list):
            raise FetchError(f"unexpected answer listing the releases of {repository}")
        for release in releases:
            if release.get("draft"):
                continue
            for asset in release.get("assets", []):
                if not asset["name"].endswith(".ck3"):
                    continue
                digest = (asset.get("digest") or "").removeprefix("sha256:")
                key = digest or asset["name"]
                if key in seen:
                    continue
                seen.add(key)
                assets.append(Asset(asset["name"], digest, asset["browser_download_url"],
                                    release.get("tag_name") or ""))
        if len(releases) < PER_PAGE:
            return assets
        page += 1


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(asset: Asset, dest: Path, token: str | None = None, opener: Opener = urllib.request.urlopen) -> bool:
    """Fetch one asset into `dest` unless it is already there. True if it was fetched."""
    target = dest / asset.name
    if target.is_file() and asset.sha256 and sha256_of(target) == asset.sha256:
        return False
    part = target.with_name(target.name + ".part")
    try:
        with opener(_request(asset.url, token, "application/octet-stream")) as response, part.open("wb") as fh:
            for chunk in iter(lambda: response.read(1 << 20), b""):
                fh.write(chunk)
    except OSError as exc:
        part.unlink(missing_ok=True)
        raise FetchError(f"cannot download {asset.name}: {exc}") from None
    if asset.sha256 and sha256_of(part) != asset.sha256:
        part.unlink(missing_ok=True)
        raise FetchError(f"{asset.name}: checksum does not match the release's")
    os.replace(part, target)
    return True


def fetch_saves(
    repository: str, dest: str | Path = "saves", token: str | None = None,
    opener: Opener = urllib.request.urlopen,
) -> list[Path]:
    """Every save on `repository`'s Releases into `dest`, plus ``releases.json``."""
    if repository.count("/") != 1:
        raise FetchError(f"a repository is owner/name, not {repository!r}")
    token = token if token is not None else os.environ.get("GITHUB_TOKEN") or None
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    assets = list_assets(repository, token, opener)
    if not assets:
        raise FetchError(f"no .ck3 assets found on any release of {repository}")
    for asset in assets:
        fetched = download(asset, dest, token, opener)
        logger.info("%s %s  [%s]", "fetched " if fetched else "ok      ", asset.name, asset.tag)
    mapping = {asset.name: asset.tag for asset in assets}
    (dest / "releases.json").write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    logger.info("%d save(s) in %s/, release tags in %s", len(assets), dest, dest / "releases.json")
    return [dest / asset.name for asset in assets]
