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


def test_no_command_prints_help_and_fails(capsys):
    assert cli.main([]) == 2
    assert "COMMAND" in capsys.readouterr().err


def test_a_bad_configuration_is_reported_not_a_traceback(tmp_path, capsys):
    (tmp_path / "ck3chronicle.toml").write_text("[sight]\n", encoding="utf-8")
    assert cli.main(["build", str(tmp_path), str(tmp_path / "site")]) == 2
    assert "unknown section" in capsys.readouterr().err


def test_build_with_nothing_to_build_exits_two(tmp_path, capsys):
    assert cli.main(["build", str(tmp_path), str(tmp_path / "site")]) == 2
    assert "no .ck3 saves under" in capsys.readouterr().err


def test_fetch_needs_a_repository(tmp_path, capsys):
    assert cli.main(["fetch", str(tmp_path / "saves")]) == 2
    assert "--repo" in capsys.readouterr().err


def test_flags_override_the_file(tmp_path):
    from helpers import make_save

    (tmp_path / "ck3chronicle.toml").write_text('[runs]\ntitle = "k_nope"\n', encoding="utf-8")
    (tmp_path / "saves").mkdir()
    make_save(tmp_path / "saves" / "a.ck3")
    assert cli.main(["build", str(tmp_path / "saves"), str(tmp_path / "site")]) == 2
    assert cli.main(["build", str(tmp_path / "saves"), str(tmp_path / "site"), "--title", "k_testland"]) == 0
