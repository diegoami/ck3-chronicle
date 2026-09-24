"""Who is harvestable. Ported from the POC's tests/test_handoff.py."""

from ck3chronicle.core.characters import living_characters
from helpers import make_save


def test_living_characters_excludes_the_dead(tmp_path):
    save = make_save(tmp_path / "a.ck3")
    # 100/101/102 are in dead_unprunable, 300 in dead_prunable, 200/201 alive
    assert set(living_characters(save, {100, 101, 102, 200, 201, 300})) == {200, 201}
    assert living_characters(save, set()) == {}


def test_a_character_in_living_but_marked_dead_is_not_harvestable(tmp_path):
    # someone who died on the save's own date can still sit in `living`
    save = make_save(
        tmp_path / "a.ck3",
        edits=(('	201={\n\t\tfirst_name="Vassal"', '	201={\n\t\tdead_data={\n\t\t\tdate=1100.6.1\n\t\t}\n\n\t\tfirst_name="Vassal"'),),
    )
    assert set(living_characters(save, {200, 201})) == {200}
