# Euclid LFO scoped integration

This is an independently tested source addition, not a change to the existing
MIDI package. Its base is published Octabam commit
`c845059dff5d0da58218b965025a174643650998` in
<https://github.com/radiohagen/octabam>. The repository-wide `octabam.json` pin
and the default staging selection remain unchanged. Euclid files have
`stage: false` in the source receipt to keep that distinction explicit.

Use a fresh, isolated Octabam worktree at that commit. From this author checkout,
copy the declared source at its native paths, then apply the small shared
integration patch:

```sh
git archive HEAD modules/euclid-lfo remixes/test/euclid-lfo \
  tools/verify/verify_euclid_lfo.py tools/verify/verify_euclid_lfo_card.py \
  tools/verify/verify_euclid_lfo_ui.py tools/verify/verify_euclid_lfo_load.py \
  tools/verify/verify_euclid_lfo_audio.py | tar -x -C /absolute/isolated-octabam-worktree
cd /absolute/isolated-octabam-worktree
git apply --check modules/euclid-lfo/integration.patch
git apply modules/euclid-lfo/integration.patch
```

The patch registers the existing STORE client callbacks and refusal entry,
adds the module-owned native probe to the existing emulator build, and declares
the stock-DSP selftest expectation. It introduces no second builder or registry.
Existing STORE clients emit identical assembly when Euclid is not selected.
Shared source remains owned by Octabam; this patch is the exact prerequisite
for the scoped snapshot, not a replacement for the repository's shared tools.

Read Octabam's AGENTS.md and BUILDING.md, initialize its submodules, and supply
your own official OS 1.40C. Run the commands in the
[module README](../modules/euclid-lfo/README.md), including project-backed panel,
card, load and audio checks. `make check REMIX=euclid-lfo OT_PROJECT=...` checks
the selected composition. These steps do not install firmware on a device.

## Composition

Selected: EUCLID LFO, STORE, and every stock FX in `remixes/test/euclid-lfo`.
Inherited: the pinned Octabam builder, native audio/MIDI routing, timing, Part
storage and emulator. Omitted: original EUCLID FX and all personal MIDI/synth
modules. Both FX slots remain available. Experimental: the entire new Euclid
LFO module, with software/emulator evidence only. PLOCKS P2 is deliberately
incompatible because its retained SRAM range overlaps; the ledger rejects it.

RATE writes existing native SPD/MULT fields. The sidecar stays at version 1;
no field or native file layout is changed. The earlier unpublished prototype
used a fixed whole-cycle period; with this revision lengths below 16 steps
run proportionally shorter cycles. Development sidecars are not claimed
sound-compatible with that earlier timing.

Exact acceptance results are recorded alongside the module in
[DECISIONS.md](../modules/euclid-lfo/DECISIONS.md). Generated audio, firmware,
screenshots, private fixtures and cards are not committed. Audio is provided
separately as listening examples, not physical-hardware evidence.
