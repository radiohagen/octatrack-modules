# MIDI ARP PRESETS test remix

Standalone [MIDI ARP PRESETS](../../../modules/midi-arp-presets/README.md), with stock
audio effects. MIDI ARP SETUP uses A for a bank of 22 editable rhythms,
B for ROOT / OCT / OCT+ on the six rolling-bass families, C for native
length and F for native key/scale. The title displays the rhythm and version.
Gate length stays under native NLEN; switching versions changes pitch only.

Build and verify: `make check REMIX=midi-arp-presets`.
This is a first implementation for emulator validation; it has not been
flashed or tested on an Octatrack.
