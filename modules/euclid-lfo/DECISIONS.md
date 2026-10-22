# Euclid LFO implementation decisions

This fixed-step revision supersedes the original bar-fitted prototype.
Evidence is image-specific; no physical-device acceptance or card installation
is claimed. Historical local prototypes are not part of this source release.

## Exact audio-clock correction (22 October 2026)

This supersedes the earlier image's timing claims below. Paired native
ColdFire + DSP audio exposed about 8 ms of accumulating offset over 16 seconds
at 120 BPM. Counts and pulse distributions matched the original EUCLID AMP
effect, but matching stock LFO timing was insufficient proof of exact steps.

Only EUCL's audio increment changes: calculate
`SPDword * tempo24 * 8 * (16 << MULT) / (496125 * STEPS)`,
carrying the fractional residue per lane. SPDword is the live signed Q8
speed, so modulation and reverse speed remain supported. Products are split
to stay within signed 32-bit arithmetic; no floating point, 64-bit divide
helper, new timer, DSP change or emulator change is needed. Both native audio
sites use this calculation. MIDI retains its already-aligned tick increment.
Residue resets on Part/bank/length changes. Native trigger/wrap/HOLD/ONE/HALF,
routing, UI, stored values, sidecar v1 and stock waveforms are unchanged.

The native probe feeds the unchanged stock audio trigger consumer an
independent 64-bit oracle increment and compares it with EUCL's complete
installed clock. This is explicitly a test-only input adapter, not a firmware
patch or a claim of stock audio phase identity. Coverage includes
100/120/137/300 BPM, fractional SPD, MULT, positive/zero/reverse speed and all
eight trigger modes. MIDI still compares directly with stock. An additional
3,696,000 sanitizer cases check exact arithmetic, modulation and bounds.

Five fresh 16-second native audio captures use the same source and fixture as
the unchanged original-effect reference. Initial FREE phase is explicitly
seeded; subsequent audio is not shifted, stretched or resynchronized.
At 120 BPM, seven steps and RATE 1/16:

- GATE with 1/3/5 pulses matches 19/55/91 recorded onsets. At 1%, 5% and 10%
  thresholds, maximum paired offset is 0.454 ms, below the predeclared
  two-block 0.726 ms limit. Last-minus-initial offset at 5% is -0.023 ms for
  all three, versus about +8 ms previously.
- ENV onsets also stay within 0.454 ms at 5%. Different gain laws remain:
  median half-peak width is 21.474 ms for old AMP and 12.630 ms for AMP VOL.
- Swing66 remains different, approximately -40.25 to +40.41 ms at 5%; this is
  not an alignment pass. Old EUCLID follows the track speed/swing mask,
  whereas the LFO uses SPD/MULT and pattern-local alternating swing.
  No global swing rewrite or destination-specific envelope compensation is made.

These are measured native emulator outputs, not pulses resynthesized as
clicks. Listening previews add only a centered quarter-note reference and a
two-second count-in, with fixed gain per implementation. Automatic PLAY
alignment, physical audio and external MIDI instrument output remain untested.

Image SHA-256:
`0e82b9b28656452348a8f72deca9e7ae9b1e3859c1c2f66a728187833ac459df`.
Runtime SHA-256:
`7e1c0139869d21c18cb65b33de65a94da69aa8c95008a5636075bbaff012a6dd`.

Author-source extraction rebuilt to both exact hashes in a separate pinned
Octabam worktree. No personal package pin, original project or device changed.

Current-image verification:

- Focused sanitizer, codec/lifecycle, routing/ABI and 69 native pixel regressions
  pass, including 24,576 trigger comparisons (3,000 HOLD and 3,942 terminal
  checks), 69,120 detour cases and 6,000-frame seven-step FREE/ONE/HALF oracles.
- `make check REMIX=euclid-lfo` passes every runnable check. General
  `verify_set` and `verify_reserve_writes` skip because no OT_PROJECT was
  supplied; the dedicated audio/load fixtures are separate evidence.
- The 6,000-frame loaded fixture passes with all 48 lanes, eight sounding FLEX
  tracks and a native Part change. Stock/EUCL instruction counts are
  27,905/36,256 per frame; EUCL peak ISR count is 73,817. The corrected build
  is about 2.9% above the earlier EUCL build's 35,222 instructions/frame.
  These are software instruction counts, not hardware cycles or headroom.
- Author source/provenance checks and 22 tests pass. Re-extracted image and
  runtime hashes match exactly. Full-panel/card suites and the 24-reference
  build matrix below remain explicitly earlier-image evidence; they were
  not rerun for this clock-only change.

## Earlier fixed-step timing revision (22 October 2026)

Each step now has a musical duration independent of STEPS: RATE 1/16 and
STEPS 7 give seven sixteenths, not seven equal subdivisions of a bar.
At 120 BPM that is 125 ms per step and 875 ms per pattern.

- Scale the native signed phase increment by 16/STEPS at both audio clock
  sites and the MIDI clock site, before native wrap and trigger handling.
  Keep signed division residue per lane; odd lengths do not accumulate
  truncation drift. Reset residue on Part/bank/length changes.
- Keep the waveform engine and Q23 phase contract. Sixteen-step timing is
  identical to the stock clock. FREE, TRIG, HOLD and SYNC still use native
  events; ONE ends after the full pattern, HALF after half (3.5 steps for 7).
- RATE occupies F on page 2. Page 1 still groups steps, pulses and accents.
  The thirteen presets use existing native SPD/MULT fields, through native
  Part/SRAM/live parameter writers. No new sidecar field or layout is added.
  Saved SPD is 0-127, not signed; reverse *runtime* increments from modulation
  remain supported. An early test assumption about negative saved SPD was
  rejected by the full native panel path and corrected before publication.
- Both native six-control layouts were rendered and reviewed again with
  RATE 1/16 and the minimum/maximum labels. The split preview stays default.
- The fixed-step focused gate adds 4.8 million host clock cases, 69,120
  installed-detour/ABI/bypass cases, and 6,000 frames per audio/MIDI complete
  native clock comparison for seven-step FREE/ONE/HALF. The original 24,576
  native clock differential cases now explicitly use STEPS 16.
- Publication is a scoped source PR in radiohagen/octatrack-modules. The
  existing personal MIDI package pin is unchanged. Shared prerequisites are
  a source patch against public Octabam c845059dff5d0da58218b965025a174643650998;
  a fresh extraction rebuilt to the identical image and runtime bytes.

Final revision image SHA-256:
`73a60441cc0f4fa8acf9be9c8f2be6766c8ca995bde46ccdfb309ae239bb4d67`.
Runtime SHA-256:
`075920f188202b18cbfdb05b480d0550cb2e04e746143349851453487a74cf2b`.

## Earlier-image software acceptance

All checks below passed on the image above, with the original input project
left unchanged. These are software/emulator results, not device acceptance.

| Check | Result |
|---|---|
| Focused engine, lifecycle, codec, installed routing/clock/ABI and pixels | PASS; 4.8 million host clock cases, 98,304 waveform calls, 77,760 destination cases, 24,576 stock clock comparisons, 69,120 detour cases and 69 pixel goldens |
| Full-boot MKII panel | PASS; 47 scenarios, including all 13 RATE presets plus STOP on both audio/MIDI, pushed unit edits, native mirrors, FREE and Part operations |
| Native FAT, SAVE PROJECT, reload, refusal choices and retained-state recovery | PASS; WAVE/SPD/MULT preserved in all 384 working/saved audio/MIDI lanes |
| Eight sounding FLEX tracks, 48 active lanes, Part change | PASS; 6,000 frames. Stock/Euclid 27,905/35,222 instructions per frame; Euclid peak frame ISR 72,569. Not a hardware headroom guarantee |
| Seven-sixteenth audio showcase | PASS; six native takes, 125 ms steps and 875 ms cycles, accent/no-clipping checks; 50-second click montage and individual clips |
| `make check REMIX=euclid-lfo OT_PROJECT=...` | All runnable checks passed. Standard MIDI CC 40/T2/FX2 fixture case skipped because that slot is NONE, not an effect in this remix |
| `scripts/refhash.sh check` | All 24 reference builds byte-identical |
| Fresh author-source extraction at the pinned Octabam base | Image and runtime hashes exactly match the tested build |
| Author repository `make check` | PASS; source/provenance checks and 22 tests |

No physical audio/MIDI instrument, hardware-cycle ceiling, arbitrary personal
remix, firmware flash or recovery was tested. No existing personal package,
card, device or default integration pin was changed. The public source contains
no generated firmware, audio samples, device project or private walkthrough.
