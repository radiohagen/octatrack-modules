# Preserve page-two locks when releasing an edited trig

## What this changes

Hold a trig, turn an FX page-two knob, then release the trig: the new lock can
be deleted by the native tap-to-clear path. Mark the held trig as edited and
clear the pending tap masks when committing its lock. A later bare tap still
clears the step and its locks. Storage format and capacity stay unchanged.

The regression uses the existing project-backed verifier. It prepares a
disposable copy with a usable FX2 in both working and saved Parts, so the
panel edits the same effect as the playback checks. No supplied project is
modified. Broader frozen-candidate and legacy-storage tests are excluded.

Modules: PLOCKS P2.
Remixes reached: octabam-bus, octabam-core, octabam-inserts.

## Why this is separate / future merges

This is an existing editor correctness bug found during Harmony/PLOCKS work.
It is required for correct page-two editing, including that future combination;
it is not a build prerequisite for Scales, Follow or Loopback. It can be
reviewed and merged independently, with no new MIDI modules.

## Measured / inferred

With the same normalized fixture and verifier, unchanged upstream loses the
lock (255, unlocked); this branch retains the edited value (3). The unchanged
upstream run fails the edit/release assertion. The corrected branch also
checks ordinary clearing, page-one preservation, copy/paste, pattern undo,
playback, save/reload, retained state and refusal of a bad companion file.

Physical button timing and LCD rendering remain unmeasured. A device losing
the lock after the same gesture would falsify the expected hardware behavior.

Base: upstream `1915559f023518700406d5e6090a164e49c8e3e7`. Branch: `codex/pr/plocks-editor`.

Extracted from completed MIDI integration `8f8e00d061d17a890a3b01d5f340492f912712e2`;
original source completion `03f7e81aee53d1d0b0c16ef1694bb10a35dcb63d`.
The complete mixed integration is not part of this PR.

## Gates (on a tree rebased onto current main)

Candidate: `e73866331bff84ad025d47beec3c20124c3ed9c3`. `BUILD=79`, `OCTABAM_PGO=0`.

- `BUILD=79 OCTABAM_PGO=0 make reach RUN=1 KEEP=1`: **PASS**, required QUICK tier.
- Shared and per-remix halves of `make check` ran through reach; no separate duplicate full-check command is claimed.
- `make test-acceptance`: not run; the acceptance runner is unchanged.
- `make accept`: not run; optional strict project-backed acceptance is outside this qualification.
- `scripts/refhash.sh check`: not applicable; no builder/toolchain change.

<details>
<summary>Generated reach commands and results</summary>

- `python3 tools/verify/verify_docs.py`: ok, 1 s.
- `make check-shared REMIXES="octabam-bus octabam-core octabam-inserts" MODULES="PLOCKS P2"`: ok, 76 s.
- `python3 tools/verify/check_shards.py --jobs 3 --modules "PLOCKS P2" octabam-bus octabam-core octabam-inserts`: ok, 492 s.

</details>

Focused checks, with `$FIXTURE` pointing to a local OS-1.40C project copied by the verifier:

- `.venv/bin/python tools/verify/verify_plocksp2.py octabam-bus --project "$FIXTURE"`: PASS, zero failures.
- `.venv/bin/python tools/verify/verify_plocksp2.py octabam-core --project "$FIXTURE"`: PASS, zero failures.
- `.venv/bin/python tools/verify/verify_plocksp2.py octabam-inserts --project "$FIXTURE"`: PASS, zero failures.
- Same bus verifier on unchanged upstream: expected FAIL at edit/release; unlocked value 255 instead of the edited lock.

Project-dependent checks skipped by the general QUICK run:

- [SKIP] verify_plocksp2: no project (OT_PROJECT=<dir> or --project)
- [SKIP] verify_scenesp2: no project (OT_PROJECT=<dir> or --project)
- [SKIP] verify_set: no project (OT_PROJECT=<dir> or --project)

PLOCKS itself was additionally exercised with a project on all three remixes as listed above; the general skips are not its only evidence.

## Hardware

Not flashed. Emulator and linked-code results do not establish MKI/MKII
button timing, card transfer or physical-device acceptance.

## Checklist

- [x] No Elektron image, slice, SysEx, sample or private project in the diff.
- [x] No submodule pin changes.
- [x] Module README and manual describe the correction and evidence boundary.
