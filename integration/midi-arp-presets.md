# MIDI Arp Presets integration

This is a separately authorized reintroduction of MIDI Arp Presets, outside
the MIDI upstream contribution series. The existing Harmony/Follow package
pin is unchanged. This source is not installed on a device.

## Source and naming

The implementation originates at local Octabam commit
`b52cd7fe1fc4e26421acc01f52f62cad0baa775d`. Its native C and hook assembly
are byte-identical here. The author-repository name follows the previous
rename: `MIDI ARP PRESETS`, `modules/midi-arp-presets`, linked unit
`midiarppresets`, and `verify_midi_arp_presets*.py`.
Generated assembly changes only its source-path header.

[sources.json](sources.json) records original and published file hashes.
The original implementation commit is retained locally; this publication
supplies module source without publishing the Octabam fork's private history.

## Scoped builder composition

Use a separate Octabam worktree at local integration baseline
`3bd99bca5d44ae6257112747070be77fef110839`, with the owner's OS 1.40C,
initialized submodules and documented toolchains. This baseline supports the
historical `mattias-bottleservice` composition. It does not qualify current
Follow/Harmony adapters or a current personal firmware package.

Copy only these author-source paths to that isolated worktree:

- `modules/midi-arp-presets/`
- `tools/verify/verify_midi_arp_presets.py`
- `tools/verify/verify_midi_arp_presets_port.py`
- `remixes/test/midi-arp-presets/`

Retire the corresponding tracked original `arp-presets` module, two
`verify_arp_presets*.py` gates and standalone test remix in that disposable
worktree. Do not leave two modules claiming the same hooks.
Update the combined remix's exact `ARP PRESETS` selector to
`MIDI ARP PRESETS` and its README link to the renamed module. The builder's historical harvest expectation in
`tools/remix/selftest.py` also needs its test-remix name updated.
Regenerate builder indexes with `make docs`. These are scoped builder
adaptations, not changes to its schema or shared runtime.

Run from the prepared builder:

```sh
.venv/bin/python modules/midi-arp-presets/generate.py --check
make bus REMIX=midi-arp-presets BUILD=79
.venv/bin/python tools/verify/verify_midi_arp_presets.py midi-arp-presets
OT_PROJECT=/path/to/local/source-project make check REMIX=mattias-bottleservice MODULES='MIDI ARP PRESETS' BUILD=79
```

The port gate owns its copied project and virtual cards. Use the workspace's
artifact-retention wrapper around the dependent commands when available.
Do not use the repository-wide historical staging helper: this module has
`stage: false` and a separate baseline.

## Verification boundary

The original `arp-presets` snapshot passed scoped `make check`, including
1,408 base applications, all three octave versions across every Part/MIDI
track, native panel operation, save/cold-load and held-root MIDI switching.
One unrelated fixture FX CC probe was skipped. Its MAIN OS SHA-256 was
`5b8070e97516fb8e1d892f2a8f55f1ccfb28efb3f23ab33d0e21acf3f9b0b436`.

The publication's exact renamed-source and combined results are recorded in
[midi-arp-presets-validation.json](midi-arp-presets-validation.json).
Source checks, emulator checks and hardware acceptance are separate.
No physical hardware, card copy or firmware installation is claimed.
