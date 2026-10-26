# Build and source integration

For current MIDI Follow, use [the dedicated integration](midi-follow.md),
which uses upstream EVENTS.

For Harmony with current Follow, use [the scoped migration review](harmony-current.md).

`octabam.json` preserves the older combined shared-event integration at
`fa5cf5eb14f2afffd934bb5ecf85b9ab9a8ed670`. Octabam owns the builder,
SEQUENCER EVENTS, EDIT EVENTS, STORE, KITS, PLOCKS and emulator. This
repository owns the module clients and musical behavior. That older integration
is not compatible with the current Follow adapter.

## Sophie source

[Sophie](../modules/sophie/README.md) is a separate experimental Synth Machine
adapter. Its manifest requires `SYNTH MACHINE` and the pinned Digisophie
submodule. The Octabam pin above qualifies Harmony/Follow; it does not include
or qualify Sophie. Build and image checks require a Sophie-enabled Octabam
integration, and physical audio acceptance remains open.

## Musical Units

[Musical Units has a separate integration recipe](musical-units.md), based on
upstream Octabam `3b3da30e`. Its source, tests, 18 screenshots and small shared
support patch reproduce the validated standalone composition. It does not
advance the Harmony/Follow pin or qualify a combined personal package.

## Historical Harmony/Follow checkout

1. Clone `https://github.com/radiohagen/octabam.git`, fetch branch
   `codex/shared-event-platform-20261021`, and create a separate worktree at
   the exact commit in `octabam.json`. Initialize its submodules.
2. Keep the author submodule at the exact commit recorded by that integration.
   Do not replace it with current author `main`: its old Follow adapter uses
   SEQUENCER EVENTS. Harmony and Follow both read that submodule, and Part
   State's copy helper also resolves there.
3. Copy `tools/verify/verify_harmony_accumulator.py` from this author checkout
   to the same path in the integration. It adds C-minor regression coverage
   while retaining the installed-event assertions. Keep the integration's
   other verifier/harness adaptations intact.
4. Follow Octabam's BUILDING.md using your own OS 1.40C. Run `make check
   REMIX=midi-harmony-follow`, standalone Follow/Harmony checks and the
   project-backed UART matrix on disposable fixtures. The matching test
   remixes select SEQUENCER EVENTS, and Harmony also selects EDIT EVENTS.

The integration and its recorded author pin reproduce historical evidence.
They do not qualify the current Follow source or alter an existing device.

The old `scripts/stage_octabam.py` workflow copies native module trees and is
for historical integrations. It now refuses to overwrite an author adapter.
Do not use it to replace this integration's manifests or shared harnesses.

`sources.json` preserves imported source provenance and current file hashes.
`make check` verifies those hashes and modes; it does not build firmware.
[Developer notes](DEVELOPMENT.md) explain source receipts.

## Recorded combined qualification

The [22 October source reconciliation receipt](midi-main-validation-20261022.json)
records the exact author source, integration base, image hashes, standalone and
combined results, C-minor regressions, all-client checks and 18-case UART matrix.
It lists project-dependent skips and hardware boundaries explicitly.

## Evidence history

The [October 19 explicit-bridge receipt](harmony-follow-validation.json) and
frozen N1 package describe older compositions. They are preserved as historical
evidence and do not qualify the shared-event source. The shared-event integration
replaces HARMONY FOLLOW and HARMONY PLOCKS; see [system events](../docs/SYSTEM_EVENTS.md).
Physical hardware acceptance remains separate from source and emulator results.
