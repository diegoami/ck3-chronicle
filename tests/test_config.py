from pathlib import Path

import pytest

from ck3chronicle.config import FILENAME, Config, ConfigError, load, parse
from ck3chronicle.wiki.prose import USER_AGENT
from ck3chronicle.wiki.site import DEFAULT_SITE


def write(tmp_path, text, name=FILENAME):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_no_file_is_the_defaults(tmp_path):
    config = load(cwd=tmp_path)
    assert config == Config()
    assert config.site == DEFAULT_SITE and config.site.companion_url is None
    assert "images" not in config.site.docs  # nobody else's delivery folder
    assert config.cache == Path(".ck3cache") and config.prose.user_agent == USER_AGENT


def test_a_named_file_that_is_missing_is_an_error(tmp_path):
    with pytest.raises(ConfigError, match="no configuration file"):
        load(tmp_path / "nope.toml")


def test_the_working_directorys_file_is_read(tmp_path):
    write(tmp_path, '[site]\ngenerator_name = "mine"\n')
    assert load(cwd=tmp_path).site.generator_name == "mine"


def test_everything_that_was_hard_wired_is_a_setting(tmp_path):
    path = write(tmp_path, '''
[site]
generator_name = "Ck-parser"
generator_url = "https://example.org/gen"
companion_url = "https://example.org/harvester/"

[site.docs]
names = "https://example.org/rule"
images = "https://example.org/images"

[saves]
repository = "someone/saves"

[runs]
title = "e_germany"
[runs.titles]
"7-1-6-1-2" = "k_testland"

[reach]
kin = false

[images]
dir = "delivered"

[cache]
dir = ""

[prose]
dir = "prose"
backend = "openai"
model = "m"
user_agent = "me/1"
''')
    config = load(path)
    assert config.site.generator_url == "https://example.org/gen"
    assert config.site.companion_label == "harvester"  # the URL's last part
    assert list(config.site.docs) == ["names", "images"]  # in the file's order
    assert config.saves_repository == "someone/saves"
    assert config.subject_for("7-1-6-1-2", "x") == "k_testland"
    assert config.subject_for("other", "x") == "e_germany"
    assert config.reach.kin is False and config.reach.family is True
    assert config.images == tmp_path / "delivered"  # relative to the file
    assert config.cache is None  # "" turns the cache off
    assert config.prose.dir == tmp_path / "prose" and config.prose.user_agent == "me/1"
    assert config.source == path


@pytest.mark.parametrize("text, message", [
    ("[sight]\n", "unknown section"),
    ('[site]\nfooter = "x"\n', "unknown key"),
    ('[reach]\nkin = "no"\n', "true or false"),
    ('[saves]\nrepository = "just-a-name"\n', "owner/name"),
    ('[prose]\nbackend = "sdk"\n', "template"),
    ("[site\n", "cannot read"),
])
def test_a_mistake_is_an_error_never_ignored(tmp_path, text, message):
    with pytest.raises(ConfigError, match=message):
        load(write(tmp_path, text))


def test_parse_takes_a_document(tmp_path):
    assert parse({}, tmp_path) == Config()
