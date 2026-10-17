# Source review map

This map describes the published author source. Counts
are for navigation, not a complexity or test-coverage claim. Generated assembly
must be checked against its C sources and generators. Original credits remain.

| Module | Files | Declared/selected dependencies |
|---|---:|---|
| [midi-scales](../modules/midi-scales/README.md) | 3 | None; optional interaction with Follow/Harmony |
| [midi-part-state](../modules/midi-part-state/README.md) | 6 | Shared native Part boundary, first consumed by Loopback |
| [midi-loopback](../modules/midi-loopback/README.md) | 7 | MIDI Part State |
| [midi-loopback-scenes](../modules/midi-loopback-scenes/README.md) | 3 | MIDI Loopback + upstream MIDI Scenes + USB MIDI |
| [midi-follow](../modules/midi-follow/README.md) | 7 | MIDI Part State; optional Scales/Loopback/Harmony |
| [midi-sram](../modules/midi-sram/README.md) | 5 | MIDI Part State; precise sparse SRAM claims |
| [midi-harmony](../modules/midi-harmony/README.md) | 63 | MIDI Part State + STORE + MIDI SRAM |
| [harmony-plocks](../modules/harmony-plocks/README.md) | 3 | MIDI Harmony + upstream PLOCKS P2 |
| [pio-write-fix](../modules/pio-write-fix/README.md) | 3 | upstream MEMORY; conflicts with STEM REC owning same fix |
| [quantizer-midi-drawer](../modules/quantizer-midi-drawer/README.md) | 3 | upstream SCALE QUANTIZER |

Shared platform work remains in the Octabam fork: STORE callback guards,
KITS header initialization, PLOCKS edit/release, sparse SRAM claim checking,
TEMPO SYNC unique symbols and emulator/test timing. These are explicit review
items, not hidden dependencies inside the author-source pin.

Harmony contains its degree engine, accumulator, UI, Chord Play, native lifecycle,
HDP4 companions and HMT2 own-step retention. This is its only implementation;
obsolete storage/UI alternatives and migration readers have been removed.
The actual upstream PR split must be proven with standalone builds before submission.

No module includes a new synth, ARP-template or POST FADER contribution.
Core upstream synth/effect modules remain present in the fork as upstream owns them.

## Harmony review units

Harmony has 1,788 lines of C across twelve module-root `*.c` files,
including SIZE and ACC. Generated assembly is reviewed beside its C/generator
input and regeneration checks; its line count should not obscure the source
logic. The remaining handwritten assembly implements native hooks and ownership.

| Review unit | Concrete source | Required boundaries |
|---|---|---|
| Chord and degree math | `harmony.s`, `voicing.s`, `size.c`, `{core,roots,packed}.c` and generated output | bounds, all keys/modes, native IDs, degree codec, register guards |
| Live play and editing | `ownership.s`, `play.s`, `chord-{part,record,ui,display,name,sequence}.s`, `{events,recording,ui}.c`, panel/hooks | Part vs playback context, note ownership, recorder handoff, UI dispatch |
| Complete persistence | `chord-files.s`, `{storage,track-retention,operations}.c`, track-retention and native copy hooks | STORE failure propagation, all tracks, corruption, clear/copy/undo, interrupted saves |
| Optional shared-module composition | `scenes.c`, `scene-access.s`, `modules/harmony-plocks/bridge.s`, KITS callbacks | unchanged PLOCKS/Scenes capacity, all KITS modes, coexistence and restart |

These are inspection units inside coherent feature stages, not permission to
ship half a lifecycle. The first usable Harmony contribution must include its
complete current MIDI TRACK storage path. Do not submit old contiguous or
packed retention as a temporary step and then require users to migrate again.
The optional PLOCKS/Scenes/KITS composition is the next stage only if the
standalone stage passes without those modules and the native lifecycle remains
complete. The final branch/test boundaries must be requalified after the
preceding PRs land.
