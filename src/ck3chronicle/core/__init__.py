"""Reading Crusader Kings III saves. Imports nothing else in the package.

Ported from diegoami/Ck-parser (the proof of concept), whose ``ck3parser``
these modules were. A docstring's "Ck-parser's PLAN.md §n" and "Ck-parser#n"
point there: its plan holds the verified facts about the save format.

Modules
-------
container   .ck3 container: plaintext header + zipped ``gamestate``.
parser      streaming Clausewitz-script tokenizer/parser.
fingerprint cheap per-file run fingerprint (header + first KB of gamestate).
runs        group snapshots into runs, order and verify them, manifest + CLI.
titles      the title index: records, histories, lieges resolved.
family      parents by inverting every child list; spouses, children.
digest      the per-save character cache.
characters  character records by id, and who is harvestable.
dynasties   houses and dynasties, their names and arms ids.
arms        coat-of-arms recipes and their digests.
cultures    cultures, named by key or by text.
faiths      faiths, named by key or by text.
player      who was played, and their primary title.
filter      referenced-vs-filler character heuristic.
realm       a ruler's realm per snapshot, depth as vassal rank.
vassalage   liege observations collapsed into stretches.
naming      the image-name rule, shared with the companion.
snapshot    one save's lineage and characters (``SnapshotView``, ``gather``).
history     a title's tenures (``holder_intervals``).
population  every character of a save, streamed (``stream_people``).
"""
