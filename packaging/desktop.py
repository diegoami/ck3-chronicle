"""PyInstaller's entry point for the Windows .exe (see .github/workflows/ci.yml)."""

from ck3chronicle.gui import main

raise SystemExit(main())
