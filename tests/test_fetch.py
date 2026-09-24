"""``ck3chronicle fetch``, against a fake GitHub: no network in the suite."""

import hashlib
import io
import json

import pytest

from ck3chronicle.fetch import FetchError, fetch_saves


class FakeGitHub:
    """Answers the releases listing and the asset downloads from memory."""

    def __init__(self, releases, files):
        self.releases = releases
        self.files = files
        self.requests = []

    def __call__(self, request):
        url = request.full_url
        self.requests.append((url, dict(request.header_items())))
        if "/releases?" in url:
            page = int(url.rsplit("page=", 1)[1])
            return io.BytesIO(json.dumps(self.releases if page == 1 else []).encode("utf-8"))
        return io.BytesIO(self.files[url])


def asset(name, data, url=None, digest=True):
    return {
        "name": name,
        "digest": f"sha256:{hashlib.sha256(data).hexdigest()}" if digest else None,
        "browser_download_url": url or f"https://dl/{name}",
    }


def test_every_release_is_read_and_each_save_fetched_once(tmp_path):
    a, b = b"save a", b"save b"
    github = FakeGitHub(
        [
            {"tag_name": "0.0.3", "assets": [asset("a.ck3", a), asset("notes.txt", b"x")]},
            {"tag_name": "0.0.2", "assets": [asset("a.ck3", a), asset("b.ck3", b)]},
            {"tag_name": "draft", "draft": True, "assets": [asset("c.ck3", b"c")]},
        ],
        {"https://dl/a.ck3": a, "https://dl/b.ck3": b},
    )
    paths = fetch_saves("someone/saves", tmp_path / "saves", token="t0ken", opener=github)
    assert [p.name for p in paths] == ["a.ck3", "b.ck3"]
    assert (tmp_path / "saves" / "a.ck3").read_bytes() == a
    releases = (tmp_path / "saves" / "releases.json").read_text(encoding="utf-8")
    assert releases == '{\n  "a.ck3": "0.0.3",\n  "b.ck3": "0.0.2"\n}\n'
    assert all(headers.get("Authorization") == "Bearer t0ken" for _, headers in github.requests)
    assert github.requests[0][0].startswith("https://api.github.com/repos/someone/saves/releases?")


def test_a_save_already_there_is_kept(tmp_path):
    data = b"save a"
    dest = tmp_path / "saves"
    dest.mkdir()
    (dest / "a.ck3").write_bytes(data)
    github = FakeGitHub([{"tag_name": "t", "assets": [asset("a.ck3", data)]}], {})
    fetch_saves("someone/saves", dest, token="", opener=github)
    assert len(github.requests) == 1  # the listing only


def test_a_download_that_does_not_check_out_is_refused(tmp_path):
    github = FakeGitHub(
        [{"tag_name": "t", "assets": [asset("a.ck3", b"what the release says")]}],
        {"https://dl/a.ck3": b"something else"},
    )
    with pytest.raises(FetchError, match="checksum does not match"):
        fetch_saves("someone/saves", tmp_path, token="", opener=github)
    assert not (tmp_path / "a.ck3").exists() and not (tmp_path / "a.ck3.part").exists()


def test_no_saves_and_no_repository_are_errors(tmp_path):
    with pytest.raises(FetchError, match="no .ck3 assets"):
        fetch_saves("someone/saves", tmp_path, token="", opener=FakeGitHub([], {}))
    with pytest.raises(FetchError, match="owner/name"):
        fetch_saves("saves", tmp_path, token="")


def test_a_listing_that_is_not_json_is_a_fetch_error(tmp_path):
    # a proxy's or an outage's HTML page answers 200 as readily as the API
    def opener(request):
        return io.BytesIO(b"<html>rate limited</html>")

    with pytest.raises(FetchError, match="cannot list the releases of someone/saves"):
        fetch_saves("someone/saves", tmp_path, token="", opener=opener)
