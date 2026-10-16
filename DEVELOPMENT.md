# MIDI Loopback and Part State author source

A narrow source branch for the matching `codex/pr/midi-loopback` contribution
in [radiohagen/octabam](https://github.com/radiohagen/octabam).

Only Loopback and its Part State dependency are included. The assembly derives
from completed integration `8f8e00d061d17a890a3b01d5f340492f912712e2`
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

## Detail-window track navigation

Track keys inherit the native input handler. One press closes the detail
window and selects the requested track; reopening captures that track as the
edit owner. The custom layer must not consume track presses or releases.
This matches the stock 1.40C TEMPO popup over MIDI NOTE SETUP, measured with
physical panel reports under the full firmware emulator. It is not hardware
acceptance. Reproduce the ownership and playback regression with Octabam's
`tools/verify/verify_midi_detail_tracks_port.py` and a disposable local fixture.
