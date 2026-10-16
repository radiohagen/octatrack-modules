# MIDI Loopback and Part State author source

A narrow source branch for the matching `codex/pr/midi-loopback` contribution
in [radiohagen/octabam](https://github.com/radiohagen/octabam).

Only Loopback and its Part State dependency are included. The assembly comes
unchanged from completed integration `8f8e00d061d17a890a3b01d5f340492f912712e2`
(original completion `03f7e81aee53d1d0b0c16ef1694bb10a35dcb63d`). The unused
Follow/Harmony NOTE SETUP staging unit is omitted. Manifests resolve assembly
relative to their own location; Octabam owns adapters, gates and test remixes.
Conditional assembly for future consumers is retained for provenance but is
not selected or qualified by this contribution.

Read [Loopback](modules/midi-loopback/README.md) and
[Part State](modules/midi-part-state/README.md). No firmware, private projects
or samples are included. Hardware acceptance remains outstanding.

`python3 tools/verify_reference.py` assembles and links the author source at
its ratified standalone placement and checks both runtime and cold-entry
hashes. GNU m68k tools must be on PATH. No firmware is needed for this check.
The cross-unit runtime is checked together because its units refer to one
another; independent `Linked.reference` links cannot resolve those references.

## Follow source addition

The Follow source is reconciled with author review commit
`86249aba3723dac0dc2a82bc278d95fcfd093d5d`, developed against Octabam
`c3f37e531f6b072b8197d93f173e063b55249363`. This branch extends the reviewed
Loopback/Part State source at `c9915c12d8e1628a096a3df20f3c0d0b71842f33`.

`make check` reproduces the existing Loopback reference and independent Follow
and Follow/Loopback references. The integration gate re-links its actual
compiled objects at the same fixed placement and compares their bytes.
No firmware is included in these references. Hardware acceptance is separate.
