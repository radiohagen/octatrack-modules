# Module catalogue

Twelve modules are imported from the Octabam fork. Source files, generators,
focused gates and native selections are retained; the source commits and original
file hashes are recorded in [sources.json](../integration/sources.json).
See [import evidence](../docs/IMPORT_EVIDENCE.md) before interpreting test status.

## Musical features

| Feature | Purpose | Maturity |
| --- | --- | --- |
| [MIDI Loopback](midi-loopback/README.md) | Per-Part EXT / INT / BOTH routing | Existing emulator evidence; hardware acceptance separate |
| [MIDI Harmony](midi-harmony/README.md) | Degree roots, chords, Chord Play, SIZE and voicing | Existing emulator evidence; hardware acceptance separate |
| [MIDI Scales](midi-scales/README.md) | Seven diatonic modes in native KEY | Existing emulator evidence; hardware acceptance separate |
| [MIDI Follow](midi-follow/README.md) | Root following, register and live response | Existing emulator evidence; hardware acceptance separate |
| [MIDI Arp Presets](arp-presets/README.md) | Editable rhythms in native MIDI ARP SETUP | Existing emulator evidence; hardware acceptance separate |
| [Sophie](sophie/README.md) | Octatrack adapter for Digisophie's FUSE voice | Experimental; original engine remains a pinned dependency |
| [Supersaw](supersaw/README.md) | Seven-saw engine, sub and drive | Experimental; mixed-engine capacity remains unqualified |
| [Post Fader](post-fader/README.md) | Optional sends following level, mute and solo | Experimental; preserves original contributor credit |

The feature name is **MIDI Arp Presets**. Its existing build selector `ARP PRESETS`
and directory `arp-presets` remain unchanged, so existing remixes and scripts
continue to resolve it. The rename does not change the instrument's native ARP UI.

## Supporting modules

| Module | Why it belongs here |
| --- | --- |
| [MIDI Part State](midi-part-state/README.md) | Shared native Part settings and coherent copy/clear handling for the MIDI features |
| [MIDI SRAM](midi-sram/README.md) | Protected retained storage for the full-capacity configuration |
| [Harmony PLOCKS](harmony-plocks/README.md) | Shared editing and copy hooks with page-two parameter locks |
| [MIDI Loopback Scenes](midi-loopback-scenes/README.md) | Routes Scenes producers through Loopback and USB destinations |

STORE, PLOCKS P2, TEMPO SYNC, Synth Machine, USB, KITS, Scenes and shared emulator
changes remain in the pinned Octabam integration tree. Their required versions
are not replaced by copying their code into this repository.

Module READMEs preserve prior verification reports as historical evidence. They
are not claims that this import has rerun every gate or qualified a new image on
hardware. Modules are composed at firmware build time; they are not device plugins.
