"""ck3chronicle: chronicles of Crusader Kings III playthroughs.

A directory of save games in, a static wiki out. ``core`` reads the saves and
imports nothing else in the package; ``wiki`` builds the pages from ``core``;
the editions (the CLI, the GitHub scaffold, the Tk window) depend on both, and
nothing depends on an edition.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("ck3-chronicle")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0+unknown"
