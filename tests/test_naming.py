"""The image-name rule: a contract with the companion, pinned.

The POC tests portraits and arms in tests/test_dynasties.py (ported as is);
this pins the realm map's name and where images live, which its wiki and map
tests relied on.
"""

from ck3chronicle.core.naming import IMAGE_DIR, realm_map_name, save_checksum


def test_a_realm_map_is_keyed_on_the_save_and_the_title():
    real = "Germania_1358_01_01.ck3"
    assert realm_map_name(real, "e_germany") == f"realm_{save_checksum(real)}_e_germany.png"
    assert realm_map_name(f"/wherever/{real}", "e_germany") == realm_map_name(real, "e_germany")


def test_images_live_in_the_chronicles_portraits_folder():
    assert IMAGE_DIR == "portraits"
