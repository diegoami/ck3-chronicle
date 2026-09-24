import pytest

from ck3chronicle.core.container import NotACk3Save, extract_gamestate, make_first_line, open_gamestate_text, read_header
from helpers import fixture_text, make_save


def test_first_line_encodes_meta_length():
    assert make_first_line(b"x" * 27387) == b"SAV01020000000000006afb\n"


def test_read_header_and_stream(tmp_path):
    p = make_save(tmp_path / "a.ck3")
    h = read_header(p)
    assert h.first_line.startswith("SAV0102") and h.unknown_field == "00000000"
    assert h.get("meta_date") == "1100.6.1"
    assert h.meta["meta_main_portrait"]["id"] == 200
    assert h.meta["dlcs"] == ["The Northern Lords", "Royal Court"]
    assert h.zip_offset == len(h.first_line) + 1 + len(h.meta_text.encode())
    with open_gamestate_text(p, h.zip_offset) as f:
        assert f.read() == fixture_text()


def test_read_header_falls_back_to_zip_scan(tmp_path):
    p = make_save(tmp_path / "a.ck3")
    data = p.read_bytes()
    first, rest = data.split(b"\n", 1)
    broken = first[:-8] + b"00000001" + b"\n" + rest  # wrong length field
    (tmp_path / "b.ck3").write_bytes(broken)
    h = read_header(tmp_path / "b.ck3")
    assert h.get("meta_date") == "1100.6.1"


def test_extract_gamestate(tmp_path):
    p = make_save(tmp_path / "a.ck3")
    out = extract_gamestate(p, tmp_path / "gamestate")
    assert out.read_text(encoding="utf-8") == fixture_text()


def test_not_a_save(tmp_path):
    (tmp_path / "x.ck3").write_bytes(b"hello\n")
    with pytest.raises(NotACk3Save):
        read_header(tmp_path / "x.ck3")


def test_the_fixture_is_the_pocs_byte_for_byte():
    # docs/PLAN.md §4: the fixture is Ck-parser's, kept byte for byte, on every
    # platform (.gitattributes keeps a Windows checkout from converting it)
    import hashlib

    from helpers import FIXTURE

    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == (
        "323e5ad1eaf2a82ae951b1191e9fb47bd2b027e9362861587099b9752830f7a1"
    )
