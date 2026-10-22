# Build and source integration

`octabam.json` pins the published Octabam shared-event integration at
`fa5cf5eb14f2afffd934bb5ecf85b9ab9a8ed670`. Octabam owns the builder,
SEQUENCER EVENTS, EDIT EVENTS, STORE, KITS, PLOCKS and emulator. This
repository owns the Harmony/Follow clients and musical behavior.

## Current Harmony/Follow checkout

1. Clone `https://github.com/radiohagen/octabam.git`, fetch branch
   `codex/shared-event-platform-20261021`, and create a separate worktree at
   the exact commit in `octabam.json`. Initialize its submodules.
2. Record the exact commit of the author checkout you are qualifying using
   `git rev-parse HEAD` here. Fetch it into the integration's
   `modules/midi-harmony/upstream` submodule and check out that commit detached.
   Harmony and Follow adapters both read that submodule. Part State's copy
   helper also resolves there. Keep the Octabam adapter manifests intact.
3. Copy `tools/verify/verify_harmony_accumulator.py` from this author checkout
   to the same path in the integration. It adds C-minor regression coverage
   while retaining the installed-event assertions. Keep the integration's
   other verifier/harness adaptations intact.
4. Follow Octabam's BUILDING.md using your own OS 1.40C. Run `make check
   REMIX=midi-harmony-follow`, standalone Follow/Harmony checks and the
   project-backed UART matrix on disposable fixtures. The matching test
   remixes select SEQUENCER EVENTS, and Harmony also selects EDIT EVENTS.

The integration pin still records the earlier author commit. Step 2 deliberately
selects the source being reviewed; record both commits and image hashes in each
new qualification. It does not alter an existing package or device.

The old `scripts/stage_octabam.py` workflow copies native module trees and is
for historical integrations. It now refuses to overwrite an author adapter.
Do not use it to replace this integration's manifests or shared harnesses.

`sources.json` preserves imported source provenance and current file hashes.
`make check` verifies those hashes and modes; it does not build firmware.
[Developer notes](DEVELOPMENT.md) explain source receipts.

## Current qualification

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
