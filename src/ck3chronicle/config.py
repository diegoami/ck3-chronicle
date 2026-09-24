"""``ck3chronicle.toml``: everything the POC hard-wired, as settings.

Every key is optional; a missing file is the defaults. Relative paths are
relative to the file. A key this module does not know is an error, never
ignored: a misspelt setting silently doing nothing is how a site ends up with
someone else's links. Secrets are never read from here: the prose key comes
from ``CK3_PROSE_API_KEY`` and a GitHub token from ``GITHUB_TOKEN``.

::

    [site]
    generator_name = "ck3-chronicle"         # the footer's "Generated ... by"
    generator_url = "https://github.com/diegoami/ck3-chronicle"
    companion_url = "https://github.com/..." # the image harvester (none by default)
    companion_name = "..."                   # its link text (default: the URL's last part)

    [site.docs]                              # portraits.json's `docs` block, in order
    names = "https://..."
    contract = "https://..."
    images = "https://..."

    [saves]
    repository = "owner/name"                # whose Releases `ck3chronicle fetch` reads

    [runs]
    title = "e_germany"                      # every run's subject (default: the player's title)
    [runs.titles]
    "576691683-1.6.1.2" = "e_germany"        # one run's, by slug or run id

    [reach]                                  # who gets a page (all on by default)
    vassals = true
    family = true
    kin = true
    siblings = true
    titled_kin = true

    [images]
    dir = "images"                           # delivered portraits, arms and maps

    [cache]
    dir = ".ck3cache"                        # per-save character digests; "" for none

    [prose]
    dir = "prose"                            # written paragraphs, read by the build
    backend = "template"                     # or "openai"
    url = "http://localhost:11434/v1"
    model = "qwen3:14b"
    user_agent = "..."
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from .wiki.prose import USER_AGENT
from .wiki.site import DEFAULT_SITE, Site

#: The file looked for in the working directory when none is named.
FILENAME = "ck3chronicle.toml"


class ConfigError(ValueError):
    """The configuration file cannot be used as written."""


@dataclass(frozen=True)
class Reach:
    """Who gets a page: the POC's ``--no-*`` flags, the other way up."""

    vassals: bool = True
    family: bool = True
    kin: bool = True
    siblings: bool = True
    titled_kin: bool = True


@dataclass(frozen=True)
class ProseSettings:
    dir: Path | None = None
    backend: str = "template"
    url: str = "http://localhost:11434/v1"
    model: str | None = None
    user_agent: str = USER_AGENT


@dataclass(frozen=True)
class Config:
    site: Site = DEFAULT_SITE
    saves_repository: str | None = None
    title: str | None = None
    titles: dict[str, str] = field(default_factory=dict)
    reach: Reach = Reach()
    images: Path | None = None
    cache: Path | None = Path(".ck3cache")
    prose: ProseSettings = ProseSettings()
    #: the file this was read from, if any
    source: Path | None = None

    def subject_for(self, slug: str, run_id: str) -> str | None:
        """The subject configured for one run, else for every run, else None."""
        return self.titles.get(slug) or self.titles.get(run_id) or self.title

    def with_(self, **changes: Any) -> "Config":
        return replace(self, **changes)


# ---------------------------------------------------------------- reading

_SECTIONS = {"site", "saves", "runs", "reach", "images", "cache", "prose"}
_SITE = {"generator_name", "generator_url", "companion_name", "companion_url", "docs"}


def _table(data: dict, name: str, allowed: set[str]) -> dict:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ConfigError(f"[{name}] must be a table")
    unknown = set(value) - allowed
    if unknown:
        raise ConfigError(f"unknown key(s) in [{name}]: {', '.join(sorted(unknown))}")
    return value


def _str(table: dict, key: str, where: str, empty_ok: bool = False) -> str | None:
    value = table.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or (not value and not empty_ok):
        raise ConfigError(f"{where}.{key} must be a non-empty string")
    return value


def _path(base: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else base / path


def parse(data: dict, base: Path, source: Path | None = None) -> Config:
    """A configuration from an already-read TOML document."""
    unknown = set(data) - _SECTIONS
    if unknown:
        raise ConfigError(f"unknown section(s): {', '.join(sorted(unknown))}")

    site_table = _table(data, "site", _SITE)
    docs = site_table.get("docs")
    if docs is not None and not (
        isinstance(docs, dict) and all(isinstance(v, str) and v for v in docs.values())
    ):
        raise ConfigError("[site.docs] must map names to URLs")
    site = Site(
        generator_name=_str(site_table, "generator_name", "site") or DEFAULT_SITE.generator_name,
        generator_url=_str(site_table, "generator_url", "site") or DEFAULT_SITE.generator_url,
        companion_name=_str(site_table, "companion_name", "site"),
        companion_url=_str(site_table, "companion_url", "site"),
        docs=dict(docs) if docs is not None else dict(DEFAULT_SITE.docs),
    )

    saves = _table(data, "saves", {"repository"})
    repository = _str(saves, "repository", "saves")
    if repository is not None and repository.count("/") != 1:
        raise ConfigError("saves.repository must be owner/name")

    runs = _table(data, "runs", {"title", "titles"})
    titles = runs.get("titles", {})
    if not isinstance(titles, dict) or not all(isinstance(v, str) and v for v in titles.values()):
        raise ConfigError("[runs.titles] must map a run's slug or id to a title key")

    reach_table = _table(data, "reach", set(Reach.__dataclass_fields__))
    for key, value in reach_table.items():
        if not isinstance(value, bool):
            raise ConfigError(f"reach.{key} must be true or false")

    images = _table(data, "images", {"dir"})
    cache = _table(data, "cache", {"dir"})
    prose = _table(data, "prose", set(ProseSettings.__dataclass_fields__))
    backend = _str(prose, "backend", "prose") or "template"
    if backend not in ("template", "openai"):
        raise ConfigError('prose.backend must be "template" or "openai"')

    cache_dir = _str(cache, "dir", "cache", empty_ok=True)
    return Config(
        site=site,
        saves_repository=repository,
        title=_str(runs, "title", "runs"),
        titles=dict(titles),
        reach=Reach(**reach_table),
        images=_path(base, _str(images, "dir", "images")),
        cache=Path(".ck3cache") if cache_dir is None else _path(base, cache_dir),
        prose=ProseSettings(
            dir=_path(base, _str(prose, "dir", "prose")),
            backend=backend,
            url=_str(prose, "url", "prose") or ProseSettings.url,
            model=_str(prose, "model", "prose"),
            user_agent=_str(prose, "user_agent", "prose") or USER_AGENT,
        ),
        source=source,
    )


def load(path: str | Path | None = None, cwd: str | Path | None = None) -> Config:
    """Read `path`, or ``ck3chronicle.toml`` in `cwd` if there is one, else the defaults.

    A named file that does not exist is an error; an unnamed one is not.
    """
    if path is None:
        candidate = Path(cwd or ".") / FILENAME
        if not candidate.is_file():
            return Config()
        path = candidate
    path = Path(path)
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except FileNotFoundError:
        raise ConfigError(f"no configuration file {path}") from None
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from None
    return parse(data, path.resolve().parent, source=path)
