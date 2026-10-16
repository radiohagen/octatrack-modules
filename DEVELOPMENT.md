# MIDI Harmony author source

This branch contains MIDI Harmony, MIDI Loopback and MIDI Part State plus MIDI SRAM.

Manifests resolve assembly relative to this repository. Octabam owns the
adapters, full-firmware tests, screenshots and test remixes. Commands naming
`tools/verify/` in module developer notes run from that Octabam checkout,
not this source repository.

## Build references

Run `make check` with GNU m68k tools on PATH. No Elektron firmware is needed.
The existing Loopback runtime and cold-entry reference remains checked by
`tools/verify_reference.py`.

`tools/verify_harmony_reference.py` independently links Harmony with Part
State in LEGACY, SHARED and MIDI TRACK layouts. `harmony-reference.json` records
the placement, units and hashes. The Octabam adapter compares its compiled
objects with the corresponding reference. The two generator checks reproduce
checked-in assembly from the Harmony and degree C sources.

## Provenance and boundaries

The starting Loopback/Part State source is
`c9915c12d8e1628a096a3df20f3c0d0b71842f33`, derived from completed integration
`8f8e00d061d17a890a3b01d5f340492f912712e2` and original completion
`03f7e81aee53d1d0b0c16ef1694bb10a35dcb63d`. The added runtime is reconciled with
author review `86249aba3723dac0dc2a82bc278d95fcfd093d5d`, developed against
Octabam `c3f37e531f6b072b8197d93f173e063b55249363`.

The load observer guard preserves valid saved roots during native bank
publication without changing the persistence format.

Reference agreement establishes source/build consistency, not hardware
acceptance. Firmware, virtual cards, private project data and samples are
not publication artifacts.

## Detail-window track navigation

Track keys inherit the native input handler. One press closes the detail
window and selects the requested track; reopening captures that track as the
edit owner. The custom layer must not consume track presses or releases.
This matches the stock 1.40C TEMPO popup over MIDI NOTE SETUP, measured with
physical panel reports under the full firmware emulator. It is not hardware
acceptance. Reproduce the ownership and playback regression with Octabam's
`tools/verify/verify_midi_detail_tracks_port.py` and a disposable local fixture.
