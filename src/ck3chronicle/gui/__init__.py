"""The desktop edition: a Tk window over :func:`ck3chronicle.api.build`.

    ck3chronicle gui            # or ck3chronicle-gui, or the Windows .exe

An edition: it depends on the library, and nothing imports it. Tk is imported
only when the window opens, so the library and the CLI never need it.

``--smoke SAVES OUT`` builds without a window and exits 0 on success: how CI
proves a packaged ``.exe`` holds everything it needs, Tk included, on a machine
where nobody can click.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def smoke(saves: str, out: str) -> int:
    """Open the real window on `saves`, close it, then build into `out`.

    The window is built and drawn, not just a Tk root: a bundle missing Tcl/Tk
    data, a ttk theme or a widget module fails here (#16).
    """
    import tkinter

    from .. import api
    from . import session
    from .app import App

    root = tkinter.Tk()
    root.withdraw()
    window = App(root, session.Settings(Path(saves), Path(out)))
    root.update()
    listed = len(window.tree.get_children())
    root.destroy()
    if not listed:
        return 1
    result = api.build(Path(saves), Path(out), session.desktop_config())
    return 0 if result.chronicles and (Path(out) / "index.html").is_file() else 1


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    # a windowed .exe has no stderr: what the library logs goes to the window
    # during a build, and nowhere otherwise
    logging.getLogger("ck3chronicle").propagate = False
    if argv[:1] == ["--smoke"] and len(argv) == 3:
        try:
            return smoke(argv[1], argv[2])
        except Exception:
            return 1
    from .app import run

    return run()
