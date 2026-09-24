import subprocess
import sys

import pytest

import ck3chronicle
from ck3chronicle import cli


def test_version_is_the_installed_distribution():
    assert ck3chronicle.__version__ != "0+unknown"


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exit:
        cli.main(["--version"])
    assert exit.value.code == 0
    assert capsys.readouterr().out.strip() == f"ck3chronicle {ck3chronicle.__version__}"


def test_runs_as_a_module():
    done = subprocess.run(
        [sys.executable, "-m", "ck3chronicle", "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert done.stdout.strip() == f"ck3chronicle {ck3chronicle.__version__}"
