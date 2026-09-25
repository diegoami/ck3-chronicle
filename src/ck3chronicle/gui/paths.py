"""Where the desktop edition looks and keeps things, per platform.

Plain functions, no Tk. Every folder is the user's own, never next to the
program: the ``.exe`` may sit in Downloads or a read-only place.

* the game's saves: ``<Documents>/Paradox Interactive/Crusader Kings III/save
  games`` on Windows and macOS, ``~/.local/share/Paradox Interactive/...`` on
  Linux;
* the chronicles: ``<Documents>/CK3 Chronicles`` unless the player picks another;
* the cache and the last build's log: the local app-data folder (large, and
  worth nothing on another machine);
* remembered choices and an optional ``ck3chronicle.toml``: the roaming one.

``<Documents>`` on Windows is asked of the shell (the Known Folder API), not
guessed as ``~/Documents``: OneDrive and folder redirection move it, and a
guess would pre-fill a folder that does not exist.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

APP = "ck3-chronicle"
GAME = Path("Paradox Interactive") / "Crusader Kings III"

#: FOLDERID_Documents
_DOCUMENTS = uuid.UUID("FDD39AD0-238F-46AF-ADB4-6C85480369C7")


def _known_folder(folder_id: uuid.UUID) -> Path | None:
    """A Windows known folder, or None when the shell cannot say."""
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        guid = GUID(
            folder_id.time_low, folder_id.time_mid, folder_id.time_hi_version,
            (ctypes.c_ubyte * 8)(*folder_id.bytes[8:]),
        )
        found = ctypes.c_wchar_p()
        shell32 = ctypes.windll.shell32  # type: ignore[attr-defined]
        if shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(found)) != 0:
            return None
        try:
            return Path(found.value) if found.value else None
        finally:
            ctypes.windll.ole32.CoTaskMemFree(found)  # type: ignore[attr-defined]
    except (AttributeError, OSError, ImportError):
        return None


def documents_dir(platform: str = sys.platform, env=os.environ, home: Path | None = None) -> Path:
    home = home if home is not None else Path.home()
    if platform == "win32":
        known = _known_folder(_DOCUMENTS)
        if known is not None:
            return known
        profile = env.get("USERPROFILE")
        return (Path(profile) if profile else home) / "Documents"
    return home / "Documents"


def default_saves_dir(platform: str = sys.platform, env=os.environ, home: Path | None = None) -> Path:
    """Where the game writes saves (it may not exist: the game may not be installed)."""
    home = home if home is not None else Path.home()
    if platform.startswith("linux"):
        data = env.get("XDG_DATA_HOME")
        return (Path(data) if data else home / ".local" / "share") / GAME / "save games"
    return documents_dir(platform, env, home) / GAME / "save games"


def default_output_dir(platform: str = sys.platform, env=os.environ, home: Path | None = None) -> Path:
    return documents_dir(platform, env, home) / "CK3 Chronicles"


def app_dir(kind: str, platform: str = sys.platform, env=os.environ, home: Path | None = None) -> Path:
    """The per-user folder for `kind`: ``"local"`` (cache, logs) or ``"roaming"`` (settings)."""
    home = home if home is not None else Path.home()
    if platform == "win32":
        var = "LOCALAPPDATA" if kind == "local" else "APPDATA"
        base = env.get(var)
        return (Path(base) if base else home / "AppData" / ("Local" if kind == "local" else "Roaming")) / APP
    if platform == "darwin":
        return home / "Library" / ("Caches" if kind == "local" else "Application Support") / APP
    var, fallback = ("XDG_CACHE_HOME", ".cache") if kind == "local" else ("XDG_CONFIG_HOME", ".config")
    base = env.get(var)
    return (Path(base) if base else home / fallback) / APP


def cache_dir(**kw) -> Path:
    return app_dir("local", **kw) / "cache"


def log_path(**kw) -> Path:
    return app_dir("local", **kw) / "logs" / "last-build.log"


def settings_path(**kw) -> Path:
    return app_dir("roaming", **kw) / "desktop.json"


def config_path(**kw) -> Path:
    return app_dir("roaming", **kw) / "ck3chronicle.toml"
