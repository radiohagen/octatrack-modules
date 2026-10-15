# Verify TEMPO SYNC's installed hook and diagnostic modes

## What this changes

Add an image gate that executes the installed TEMPO SYNC hook and checks all
eight track records, the FX2 ID writer, held/released notes, unrelated bytes,
stack balance and preserved registers. Check the OFF hook against stock and
execute REPLAY without note publication. Register the gate with TEMPO SYNC.

Modules: TEMPO SYNC (test registration only).
Remixes reached by the required quick check: octabam-bus. Additional focused
builds: bus-notempo and bus-tempo-replay.

## Why this is separate / future merges

**Additional regression coverage, not a required fix or merge prerequisite.**
Upstream already fixed the generic-symbol collision in `b2a35a5` by resolving
symbols within their owning linked unit. The original proposed symbol rename
is therefore dropped. Firmware code and symbol names stay upstream's; this
PR tests the final installed behavior in addition to the linker unit tests.
MIDI Scales and later MIDI features do not depend on this test PR.

## Measured / inferred

The gate fails on upstream `b3dc3d7` (immediately before the linker fix): the
installed jump targets another unit. The same gate passes on current upstream
and on this branch. Normal, OFF and REPLAY selections pass. Firmware identity
against current upstream is measured separately from the historical failure.

Coverage is at the installed ColdFire hook, not external MIDI clock timing,
physical USB behavior or audio quality. A wrong hook, incorrect FX2 ID or
unexpected record/register write fails the gate.

Base: upstream `1915559f023518700406d5e6090a164e49c8e3e7`. Branch: `codex/pr/tempo-hook-symbols`.

Extracted from completed MIDI integration `8f8e00d061d17a890a3b01d5f340492f912712e2`;
original source completion `03f7e81aee53d1d0b0c16ef1694bb10a35dcb63d`.
The complete mixed integration is not part of this PR.

## Gates (on a tree rebased onto current main)

Candidate: `4aa321d4f5ef1c429265b4951df4a4f24eeda611`. `BUILD=79`, `OCTABAM_PGO=0`.

- `BUILD=79 OCTABAM_PGO=0 make reach RUN=1 KEEP=1`: **PASS**, required QUICK tier.
- Shared and per-remix halves of `make check` ran through reach; no separate duplicate full-check command is claimed.
- `make test-acceptance`: not run; the acceptance runner is unchanged.
- `make accept`: not run; optional strict project-backed acceptance is outside this qualification.
- `scripts/refhash.sh check`: not applicable; no builder/toolchain change.

<details>
<summary>Generated reach commands and results</summary>

- `python3 tools/verify/verify_docs.py`: ok, 49 s.
- `python3 tools/verify/verify_bus.py --base origin/main`: ok, 23 s.
- `make check-shared REMIXES="octabam-bus" MODULES="TEMPO SYNC"`: ok, 171 s.
- `python3 tools/verify/check_shards.py --jobs 2 --modules "TEMPO SYNC" octabam-bus`: ok, 132 s.

</details>

Focused checks:

- `make bus REMIX=octabam-bus` then `.venv/bin/python tools/verify/verify_tempo_publish.py octabam-bus`: PASS.
- `make bus REMIX=bus-notempo` then `.venv/bin/python tools/verify/verify_tempo_publish.py bus-notempo`: PASS.
- `make bus REMIX=bus-tempo-replay` then `.venv/bin/python tools/verify/verify_tempo_publish.py bus-tempo-replay`: PASS.
- Historical upstream `b3dc3d7`, same bus build/gate: expected FAIL at the installed target; current upstream control passes.
- Candidate and current-upstream bus images: byte-identical, SHA-256 `d7bfd26a85f23ce86993e3b124d5455585cc8d97c4ffa531285a4855b20de662`.

One initial QUICK run failed the existing USB full-speed packet-size check (176/192 bytes instead of 344–368). The identical-firmware upstream control passed, and the required reach rerun passed without code changes; 12 of its 13 per-remix jobs reused passing identical-image/input results, while USB reran. The cause of that transient result has not been established; the original failure is retained in the qualification record.

Project-dependent checks skipped by the general QUICK run:

- [SKIP] verify_set: no project (OT_PROJECT=<dir> or --project)

## Hardware

Not flashed. No new hardware result is claimed or required for this test-only
change; existing upstream module hardware attribution is preserved.

## Checklist

- [x] No Elektron image, slice, SysEx, sample or private project in the diff.
- [x] No submodule pin changes.
- [x] Module README separates upstream's fix from the additional test coverage.
