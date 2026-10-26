# Euclid LFO implementation decisions

This fixed-step revision supersedes the original bar-fitted prototype.
Evidence is image-specific; no physical-device acceptance or card installation
is claimed. Historical local prototypes are not part of this source release.

## Bus composition retention

The bus remix explicitly selects SIDECAR. It leaves PLOCKS P2, MIDI Scenes,
KITS and Harmony retained allocations unchanged. Unsaved LFO edits are not
restored after power-off. The existing file codec and STORE refusal handling
remain in use; no second file format or journal is introduced.

## Blank LFO SETUP after startup (23 October 2026)

RADBUSR1 was reported to show a blank LFO details page. The released image
`9ec04860bc0098f9a7723c6483b7aad27947ebc23ee102dd51fffd44b421831e`
reproduces blank native SETUP and Euclid editor pages on both audio and MIDI
when its redraw guard, `rate_writing` at `0x4114528c`, is preloaded nonzero
before boot. The same image draws them with that word initially zero; NO
still exits in the failing test. This demonstrates a real defect, not a
readback of the reported device's memory.

The loader deliberately does not clear BSS. C's explicit zero initializers
were therefore insufficient for several small state variables. In particular,
the new redraw guard suppressed the entire native/Euclid drawer from startup.
Previous tests started on zero-filled emulator RAM and asserted settings
while only recording, not rejecting, blank panel screenshots.

Both retention variants now use `-fno-zero-initialized-in-bss`, matching the
existing generated-module convention. Generation rejects remaining BSS/COMMON
symbols. The sidecar build moves 84 bytes from BSS to loaded data, with the
same text size and total module storage; no rhythm, encoder, native field or
sidecar-format change. A negative source test restores the old compiler
behavior and requires rejection in both variants.

The panel gate gains stock-wave SETUP cases, visible-popup assertions and
`--dirty-start`: all 35 writable variables (83,524 bytes in the sidecar
build) are dirtied before the actual loader executes, not reset by the test
after boot. The original RADBUSR1 fails this gate with zero popup ink.
The fixed combined image passes 12 selected audio/MIDI scenarios under both
clean and dirty starts (24 cases): stock SETUP, EUCL-selected SETUP, editor
pages 1/2, rapid/held encoder bursts and above-maximum RATE correction.
All 12 clean/dirty rendered PNGs and result records match exactly.

Author source checks pass all 26 tests, provenance and both generated variants.
The direct `verify_euclid_lfo.py radio-bus` gate passes on this exact candidate:
sanitized engine/clock/codec/lifecycle checks, installed audio/MIDI timing and
routing, native Part operations, sidecar no-SRAM-write checks and all 69
unchanged LCD pixel regressions.
The broader `make check REMIX=radio-bus BUILD=R1 MODULES='EUCLID LFO'`
run was deliberately interrupted after over 25 minutes in the unrelated
Harmony SIZE matrix. Completed gates had no failures, including boot/runtime
readback, DSP dirty-state/init, remix switching, USB and multiple MIDI/Part
checks; project-backed gates were explicitly skipped without OT_PROJECT.
That interrupted run is not a complete package qualification.

Candidate MAIN OS SHA-256:
`f070bbe950bcce8b6206c70fde196bb862e2683cecab26aa89d3771dad2ac17e`.
Runtime SHA-256:
`e62168b185fb0af730dbf9f505fe3fb45393865538e67b1a5a3e993223b9d78a`.
This is a local candidate based on the RADBUSR1 composition, not a replacement
published package or a device installation. Physical acceptance remains open.

## Encoder response and bounded CPU work (23 October 2026)

The user reported overly fast, possibly laggy/inconsistent controls. The
editor previously applied every raw panel count directly, even to two/four-way
choices, and redrew the whole page on unchanged values. Each real edit also
recomputed and committed all 48 retained records in its Part.

- Field-specific resistance is documented in README: four counts for pattern
  counts/rotation/rate, eight for OUT/DIR, two for swing and one for 0–127
  continuous amounts. No acceleration; unused motion is bounded and cleared
  at limits, direction changes, page changes and reopen. Native encoder state
  is not borrowed. Existing value ranges, dependent clamps, mode meanings,
  six-control layout, waveform and persistence formats remain unchanged.
- No-change/sub-threshold events do not redraw, dirty or write settings. RATE
  suppresses intermediate native-writer redraws and draws once after both
  SPD and MULT are updated. Other controls no longer perform RATE lookups.
  Turning down from VAR above the fastest preset now enters 64T instead of
  skipping to 1/64. Boundary panel tests cover both ends on audio and MIDI.
- A knob edit commits only its lane's retained record. Whole-Part lifecycle
  operations retain their existing path. The same ticket/revision guards,
  invalidation-before-write, per-record CRC and save-as re-keying are used.
- A 768-byte audio-clock coefficient cache removes repeated divisions while
  live speed, tempo, multiplier and length stay unchanged. Any changed input
  recalculates immediately. Signed carry and reverse/stop transitions remain
  bit-exact with the original uncached arithmetic, retained as a test oracle.

Measured under the ColdFire port, not hardware cycles:

| Workload | Before | After |
|---|---:|---:|
| Already-clamped editor turn, journal uninitialized | 32,422 instructions | 298 |
| Zero-delta editor event | 32,002 instructions | 292 |
| Retained edit, all 48 records versus one record | 61,973 instructions | 3,650 |
| 127 steady clock calls | 4,572 instructions / 635 long divisions | 4,495 / 0 |
| 127 continuously changing clock calls | 4,572 instructions / 635 long divisions | 7,633 / 635 |

The cache deliberately trades extra miss-path instructions for division-free
steady updates; it is not a claim that all workloads get fewer instructions.
The 6,000-frame, 48-lane/eight-FLEX loaded test passes with 36,292 instructions
per frame, versus 36,256 on the prior image with the same source project;
peak ISR is 74,513 versus 73,817. Stock comparison remains 27,905 per frame.
Instruction counts do not price hardware division latency or establish spare
hardware headroom. Physical knob feel and hardware CPU cost remain unverified.

Image SHA-256:
`42707abc4dcdf368a09c1471eb3e085701cf4df6d8abbd6aa85d77f30beec323`.
Runtime SHA-256:
`a03a88c12b60ae92d377c5b57ad7c2bb6d12969b4bd4cf228fb9ffb8825e65ba`.

Focused validation passes 2,262,400 cached/original clock comparisons plus the
existing independent 64-bit clock tests, installed native routing/trigger
checks and all 69 unchanged LCD goldens. Encoder checks include all fields,
signed slow/coalesced motion, endpoint reversal, held pushes, inactive fields
and partial-turn isolation between pages/reopens. All 384 retained lane
records recover independently without changing neighbouring records.
The linked integration test additionally checks whole-Part publication with
retention enabled, then an actual native encoder edit: 34,410 instructions
including the journal and redraw, with neighbouring records unchanged.
The bulk `eul_changed(bank,part)` entry retains its whole-Part contract; only
the private editor path supplies a lane-specific change.
`make check REMIX=euclid-lfo` passes every runnable gate. General `verify_set`
and `verify_reserve_writes` skip without OT_PROJECT. The final image passes the
6,000-frame DSP-loaded fixture and four new audio/MIDI RATE boundary scenarios.
The complete 47-scenario UART panel suite and native FAT/STORE/power-up suite
pass on preceding image
`6d93ba97bff470df60058a2811d468437352e7b3a0e09ee2be89c91363c294cb`;
only the out-of-range VAR-to-preset selection changed afterward. Those full
panel/card results remain explicitly prior-image evidence, not a rerun of
every lifecycle scenario on the final RATE-only correction.
No device, personal firmware package or project has been modified.

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
