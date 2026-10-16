# MIDI Follow author source

This branch contains MIDI Follow, MIDI Loopback and MIDI Part State.

Manifests resolve assembly relative to this repository. Octabam owns the
adapters, full-firmware tests, screenshots and test remixes. Commands naming
`tools/verify/` in module developer notes run from that Octabam checkout,
not this source repository.

## Build references

Run `make check` with GNU m68k tools on PATH. No Elektron firmware is needed.
The existing Loopback runtime and cold-entry reference remains checked by
`tools/verify_reference.py`.

`tools/verify_follow_reference.py` independently links Follow with Part State,
and Follow with Loopback, at their recorded reference placement. The Octabam
adapter re-links its compiled objects there and compares the bytes. This branch
includes the NOTE SETUP confirmation hook required by Follow.

## Provenance and boundaries

The starting Loopback/Part State source is
`c9915c12d8e1628a096a3df20f3c0d0b71842f33`, derived from completed integration
`8f8e00d061d17a890a3b01d5f340492f912712e2` and original completion
`03f7e81aee53d1d0b0c16ef1694bb10a35dcb63d`. The added runtime is reconciled with
author review `86249aba3723dac0dc2a82bc278d95fcfd093d5d`, developed against
Octabam `c3f37e531f6b072b8197d93f173e063b55249363`.

Reference agreement establishes source/build consistency, not hardware
acceptance. Firmware, virtual cards, private project data and samples are
not publication artifacts.
