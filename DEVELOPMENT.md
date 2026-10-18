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

## Resident activation

The post-loader activation body is also linked into the OS entry unit. Its
callback addresses are mandatory `Linked.runtime_refs`, resolved from the
selected runtime rather than frozen addresses. The declared `defsyms` values
describe the standalone reference only. The original runtime body is retained
unused to preserve runtime placement during validation. The standalone oracle
links the runtime first, then resolves the resident body's operands from it.

This keeps native startup order and DSP upload code unchanged. A placement
prototype passed initial and requested cold startup with all module hooks
enabled; the physical failure mechanism and repeated final-image hardware
acceptance remain open. Octabam's activation gate compares registers, status,
stack and callback stores before the native continuation, and rejects a
deliberately corrupted callback. The build refuses missing providers, changed
resident size or moved exports.

## Detail-window track navigation

Track keys inherit the native input handler. One press closes the detail
window and selects the requested track; reopening captures that track as the
edit owner. The custom layer must not consume track presses or releases.
This matches the stock 1.40C TEMPO popup over MIDI NOTE SETUP, measured with
physical panel reports under the full firmware emulator. It is not hardware
acceptance. Reproduce the ownership and playback regression with Octabam's
`tools/verify/verify_midi_detail_tracks_port.py` and a disposable local fixture.

## MIDI playback context

Sequenced routing reads each MIDI track's applied bank and Part
(`0x8000666e + track` and `0x80006676 + track`). Stock publishes these when
it applies that track's setup. Unlatched tracks use the applied engine Part,
as stock does. Global setup-message latches can lag the first notes after PLAY. Audio voices can
retain a previous Part, and the UI can select a Part before playback changes;
neither is an authority for sequenced MIDI. Live keys keep their UI context,
and the native bank/program sender keeps its explicit bank/Part arguments.

`verify_midi_loopback_context.py` exercises all eight tracks, EXT/INT/BOTH,
conflicting retained audio Parts and future UI selections, first/last banks,
invalid contexts, and original-note release on actual MIDI context changes.
The native companion `verify_midi_loopback_transitions.py` replays A03 EXT to
A02 INT with and without an audio T1 trig, stopped and running, using a local
v23 LB-CHECK/LB-FRESH fixture. It checks actual external note messages and
internal delivery, rather than accepting the UI label as routing proof.
