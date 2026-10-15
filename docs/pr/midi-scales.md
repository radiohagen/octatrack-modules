# Add seven-mode MIDI Scales to the native ARP KEY control

## What this changes

Extend MIDI ARP SETUP's KEY control with Dorian, Phrygian, Lydian, Mixolydian
and Locrian in all twelve keys. OFF and the existing Major/Minor IDs retain
their meaning and original output path. New modes snap to the nearest scale
note, with ties downward. Encoder order groups the seven modes by key.

Use the existing Part field and native setter. No new companion file or
storage format is introduced. Older firmware cannot interpret choices 25–84;
select OFF or an original Major/Minor choice before using that Part on stock.
Audio-track Scale Quantizer is independent.

Modules: MIDI SCALES, with stock effects in its test remix.
Remixes reached: midi-scales; octabam-core as the shared-check floor.
Official user remix selections are unchanged.

## Why this is separate / future merges

**Standalone feature.** It needs neither the PLOCKS fix nor the TEMPO test PR,
nor Follow, Loopback or Harmony. Future features can compose with it in their
own contributions; no combination acceptance is claimed by this PR.

The public author submodule is pinned to
[`9d31ce2ff977205bdd3c17a58e55f86bc11376ac`](https://github.com/radiohagen/octatrack-modules/commit/9d31ce2ff977205bdd3c17a58e55f86bc11376ac).
That commit contains only Scales and its documentation/licence, so its entire
source is reviewable alongside this adapter. The assembly matches the finished
implementation; the manifest resolves its source relative to itself.

## Measured / inferred

The gate checks 84 key/mode combinations over 128 notes; installed output
across eight tracks, 85 KEY choices including OFF, and all 128 notes; legacy
continuation paths, encoder order and clamps, formatter bounds, surrounding
bytes and preserved registers. No Follow/Harmony-only test helpers are included.

Native and author-adapter BUILD=79 images are byte-identical. The adapter's
standing `Linked.reference` checks the 870-byte author runtime at `0x40a955e0`;
a deliberately wrong reference fails the build. Source drift cannot silently
change that baseline. The public submodule is independently cloneable.

Native Part persistence is reused; this linked-code gate does not establish
full project save/reload, physical encoder feel, LCD appearance or hardware
MIDI timing. Those remain explicit device/integration acceptance boundaries.

Base: upstream `1915559f023518700406d5e6090a164e49c8e3e7`. Branch: `codex/pr/midi-scales`.

Extracted from completed MIDI integration `8f8e00d061d17a890a3b01d5f340492f912712e2`;
original source completion `03f7e81aee53d1d0b0c16ef1694bb10a35dcb63d`.
The complete mixed integration is not part of this PR.

## Gates (on a tree rebased onto current main)

Candidate: `16d8c7daab86292a3a85573971613d03bec9261a`. `BUILD=79`, `OCTABAM_PGO=0`.

- `BUILD=79 OCTABAM_PGO=0 make reach RUN=1 KEEP=1 TESTS=1`: **PASS**, required QUICK tier.
- Shared and per-remix halves of `make check` ran through reach; no separate duplicate full-check command is claimed.
- `make test-acceptance`: not run; the acceptance runner is unchanged.
- `make accept`: not run; optional strict project-backed acceptance is outside this qualification.
- `scripts/refhash.sh check`: not applicable; no builder/toolchain change.

<details>
<summary>Generated reach commands and results</summary>

- `python3 tools/verify/verify_docs.py`: ok, 1 s.
- `make check-shared REMIXES="midi-scales octabam-core" MODULES="ATA WRITE GUARD,BATCH_BUGFIXES,BRAIN,CC FEEDBACK,CC MAP,CHORUS,COMB FILTER,COMPRESSOR,DARK REV,DELAY,DIRECT_JUMP_KYOTI,DJ EQ,EQUALIZER,ERASE_EMPTY_TRIGLESS_LOCKS,FILTER,FLANGER,KITS,LO-FI,LOFI AMF FIX,MEMORY,MIDI SCALES,MIDI SCENES,MUTE_MODES,PHASER,PLATE REV,PLOCKS P2,QUANTIZE_LIVE_REC_TOGGLE,RECORDER LOOP FIX,REC_TRIG_MUTE,RELOAD_FROM_PROJECT,REMIX SWITCH,RLEN PLEN,SCALE QUANTIZER,SCENES P2,SPATIALIZER,SPRING REV,STORE,TUNER,USB"`: ok, 73 s.
- `python3 tools/verify/check_shards.py --jobs 3 midi-scales octabam-core`: ok, 301 s.

</details>

Focused checks:

- `.venv/bin/python tools/verify/verify_midi_scales.py midi-scales`: PASS, including installed output and encoder paths.
- Native-source versus pinned-adapter standalone build: identical SHA-256 `d3a2476762978a946d1733c2f153ea23ab67b81ee40017d0349e2cbc65a3edcf`.
- Valid author reference: build passes; deliberately corrupted reference: build refuses as expected.
- Local `midi-scales-bus` selection (current official bus plus Scales): build, standing reference, installed Scales gate and TEMPO installed-hook gate pass. This is focused composition coverage, not a full combined acceptance run or a proposed new user remix.

Project-dependent checks skipped by the general QUICK run:

- [SKIP] verify_brain: no project (OT_PROJECT=<dir>, --project or ~/.octabam_project)
- [SKIP] verify_kits: no project (OT_PROJECT=<dir> or --project)
- [SKIP] verify_plocksp2: no project (OT_PROJECT=<dir> or --project)
- [SKIP] verify_reserve_writes: no project (OT_PROJECT=<dir> or ~/.octabam_project)
- [SKIP] verify_scenes: no project (--project, OT_PROJECT or ~/.octabam_project)
- [SKIP] verify_scenesp2: no project (OT_PROJECT=<dir> or --project)
- [SKIP] verify_set: no project (OT_PROJECT=<dir> or --project)

## Hardware

Not flashed. No card transfer, physical MIDI or device-acceptance claim.

## Checklist

- [x] No Elektron image, slice, SysEx, sample or private project in the diff.
- [x] Public author pin and reason are stated, with the full source diff linked.
- [x] Module README and manual distinguish measured behavior from limits.
