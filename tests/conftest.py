import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))  # for `helpers`


@pytest.fixture(autouse=True)
def _in_tmp_path(tmp_path, monkeypatch):
    """Every test runs in its own directory.

    A build caches digests in ``./.ck3cache`` and reads ``./ck3chronicle.toml``
    by default: neither may leak between tests or into the checkout.
    """
    monkeypatch.chdir(tmp_path)
