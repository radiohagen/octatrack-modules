# Supersaw

## S13 final CPU pass

S13 preserves S12 sound, four independent voices and both FX slots. Dry mono
and single-voice playback skip unused filter-parameter setup once the wet fade
has ended. Native stereo output combines Q15 gain truncation with 16.16 output
formatting, and a retired poly track clears its fixed-size native buffer with
less loop overhead. Short and split calls retain their original bounds.

The output conversion keeps negative fractional rounding and uses unsigned
formatting for a defined 32-bit result even when old filter history overshoots
during bypass. Source checks cover all 81,920 values in the interpolation range at seven
AMP gains (1,146,880 PCM/stereo comparisons), plus 2,048 extreme-history
blocks, against an independent wide-arithmetic oracle. Retired-note tests
check every supported buffer length, 0–32, including guards and counters.

The final linked S12/S13 profile improves all 640 isolated cases and all 54
sustained phase means/peaks. Rich dry mono uses 4.2–5.3% fewer instructions;
a single active poly note uses 6.0–7.0% fewer. A fully retired poly call falls
from 136 to 107 instructions (21.3%). Dense four-note playback gains only three
instructions per track per call in this pass; its larger filter savings come
from S9–S12. These are executed instructions, not hardware cycles or total CPU.

Normal mono/multi-voice stack maxima stay at 388/520 bytes; singleton poly adds
four bytes (328 to 332). Odd/split maxima remain 404 mono, 536 poly and 692 mono
with poly tails. Supersaw function text grows 704 bytes to 37,016; mutable state and tables remain
unchanged. Compared with S11, 542 of 560 audible cases improve; 18 dry multi-note
attack/release cases still increase, by at most 59 instructions (2.4%).

Exact linked comparison retains 140,916 stereo samples over 4,512 blocks,
plus 7,200 paired calls in the extreme-history/bypass gate, including filter
warm-up. The focused native
suite exercises mono-plus-triad bursts, dual filtered four-note tracks,
mono/poly transitions and adding/editing T4 beside synthetic Thru/kick tracks.
Hardware timing and the original physical crash remain unverified.

## S12 scenario-aware CPU candidate

S12 retains S11 samples, filter response, controls, four independent voices
and both FX slots. It removes redundant work without reducing the sample rate,
shortening releases or changing the patch format.

- The per-voice SEM filter uses the **ColdFire CPU EMAC**, not either audio DSP.
  Coefficients and ramps scale once per block; each wide Q14 multiplication
  keeps its exact signed rounding. All caller EMAC state is preserved, including
  MACSR, accumulator extensions and rounding flags. OFF/empty calls skip setup.
- Held AMP blocks skip ramp arithmetic, and mono unity skips amplitude multiplies.
- A polyphonic track currently playing one native voice writes stereo directly.
  It still accepts up to four notes; multiple voices and carried release tails
  use the ordinary saturating mixer.
- Pitch and timbre preparation have separate dirty checks. Symmetric detune needs
  one offset calculation, and bank selection takes three bounded comparisons.
- SUB=0 uses the exact constant saw weight and advances the unused sub phase once
  per block. Enabling SUB later resumes at the same phase.
- Unrelated synth starts skip dormant Supersaw initialization. Mono-to-poly carry
  uses aligned structure copies. Pure mono rendering skips the poly scratch frame.

The reusable EMAC gate checks 10,000 products and 8,000 full/half-rate filter
blocks against an independent scalar reference, with arbitrary incoming
accumulators, extensions and MACSR flags. Linked comparison against frozen S11
also covers sustained controls, sparse voices, mixed envelopes, feature toggles,
filter bypass/resume and odd/split blocks. These are software arithmetic and
state checks, not hardware timing or proof that the original crash is resolved.

Run the linked gates with Octabam's corrected Unicorn library through
`LIBUNICORN_PATH`. They fail closed when its EMAC arithmetic self-test fails.
Production lifecycle diagnostics remain off. A source-qualified S12 candidate
still needs guarded device timing and the real Thru/kick pattern replay.

The linked S11/S12 comparison measures executed CPU instructions for the same
16-sample calls. Two-track rows use four voices on each track and SUB/DRIV on;
filter-sweep means cover 256 sustained frames. These are renderer costs, not
whole-device CPU percentages or hardware cycles.

| Case | S11 instructions | S12 instructions | Reduction |
| --- | ---: | ---: | ---: |
| Two tracks, filter OFF | 6242.75 | 6006.75 | 3.8% |
| Two tracks, LOW sweep | 12062.72 | 10997.34 | 8.8% |
| Two tracks, BP sweep | 11783.53 | 10381.10 | 11.9% |
| Two tracks, HP sweep | 11852.47 | 10446.85 | 11.9% |
| One active poly voice, held, OFF | 1093 | 855 | 21.8% |
| Four-voice first attack, LOW | 7485 | 6502 | 13.1% |
| Mono-to-poly history copy | 325 | 74 | 77.2% |

Across 640 isolated render probes, 595 improve and 45 increase. The largest
absolute increase is 62 instructions (2.5%) on a dry four-voice release; the
largest audible relative increase is 28 instructions (4.2%) on a dry mono
release. Retired poly calls increase from 124 to 136 instructions. Sustained mixed-gain tests retain
the improvements on audible filtered paths; zero-gain/retired overhead does not
render oscillators. Regular-frame stack peaks fall from 692 to 388 bytes for
mono and 536 to 520 for poly. Separate odd/split probes fall from 708 to 404 for
mono, 552 to 536 for poly, and 708 to 692 for mono with poly release tails.
These stack measurements exclude surrounding OS callers and interrupts.

The specialized paths grow linked Supersaw text from 31,934 to 36,312 bytes
(+4,378 bytes); mutable state and tables are unchanged. Instruction-cache and
bus effects of this tradeoff require hardware measurement. EMAC operations are
counted separately from scalar multiplies; replacing a multiply sequence does
not remove the underlying multiplication work.


## S10 lifecycle CPU candidate

Hardware testing of S9 found burst-start pressure even with TYPE OFF: one
four-note host MIDI packet exceeded the nominal frame interval. This candidate
preserves S9 sound, four voices, independent releases, all controls, and both FX
slots. It does not claim that the hardware overload or earlier crash is solved.

- Cold retriggers reset oscillator/resampler history while retaining valid
  derived coefficients. Pitch and controls are checked before reuse.
- Native 16-sample poly AMP ramps use Q4 instead of Q16 with identical samples;
  short/split calls retain the original exact arithmetic.
- A 384-byte, 32-entry cache stores the native pitch conversion keyed by the
  final slewed word. RATE is fixed to unity in this native routine, so FINE,
  GLIDE and modulation remain represented by the key. Collisions recompute;
  non-Supersaw tracks retain the native conversion. Hits cost 18 instructions
  versus 56.2 on average over 1,814 tested words; misses add about 24 instructions.
- A selected poly track with no active native voices skips mix/control setup.
  Audible release tails still use the native gain law and retirement threshold.

The final linked renderer comparison against S9 uses four rich voices, 16
output samples, and identical state/control inputs:

| Renderer case | S9 instructions | S10 instructions |
| --- | ---: | ---: |
| First attack, OFF | 4134 | 4024 |
| Repeated attack, OFF | 4134 | 3688 |
| First attack, LOW | 8125 | 8020 |
| Repeated attack, LOW | 8105 | 7664 |
| Release, OFF | 3694 | 3616 |
| Held, OFF | 3375 | 3397 |
| Held, LOW | 6190 | 6217 |
| No remaining poly voices | 386 | 123 |

The held renderer has a small overhead increase (0.4–0.7%); the separate native
pitch cache saves work outside this renderer measurement. Do not add those
figures into a hardware CPU percentage. First-start savings are much smaller
than repeated-attack savings. Sampled stack peaks are 700 bytes for the nested
mono adapter and 548 for poly, versus S9's 692 and 540 respectively. These
exclude the surrounding OS stack and do not establish device stack headroom.
The diagnostic probe costs 52 instructions per event and 99 additional
instructions for a silent render snapshot in the isolated fixture. Actual
cache/bus/interrupt cost on hardware remains unmeasured.

### Optional lifecycle observation

Production builds contain no diagnostic counters, hooks or timer reads. For an
isolated diagnostic integration, run `SS_DIAGNOSTICS=1 python3
modules/supersaw/generate.py`, then build with `SS_DIAGNOSTICS=1` in the environment
as well. Restore the checked-in production assembly with the ordinary generator
before committing. The same setting must be used for generation and composition.

`diagnostics.h` defines the fixed layouts, and linked symbols locate them:

- `ss_diag_events`: two 64-record rings. MIDI enqueue/off events use ring 0;
  audio allocation/activation/selector events use ring 1. Each record contains
  sequence, native frame, DTCN3 tick, kind, zero-based track, note/identity,
  selected flag and note stamp. Kind 1=enqueued note, 2=accepted note-off,
  3=poly allocation attempt (may be absorbed as a duplicate), 4/5=allocator
  entry/exit, 6=selector completed. Audio activation identities retain their
  native high bit; these are attempts, not proof of audible output. Inspect
  the native voice ages/states too. The generic Synth hooks also observe
  non-Supersaw events, distinguished by the selected flag (which may still be
  zero on the first enqueue before marker resolution).
- `ss_diag_tracks`: per-track frame/sample count, mono/poly state, native
  target gains, previous gains at render entry, four voice states/ages, and
  all five filter wet amounts. Native voice state 0=free, 1=held, 2=releasing,
  3=fading. A positive release gain is not a stuck voice by itself.
- `ss_diag_costs`: calls/last/max/sum in DTCN3 ticks for selector/config/reset,
  renderer/mix, and native allocator. DTCN3 runs at 132 MHz, as in LOAD METER.
  Interrupts and bus delays are included. Read counters as a consistent stopped
  snapshot or retry; sums wrap modulo 2^32. Renderer durations exclude snapshot
  copying but the diagnostic build still pays that copying cost in its frame.
  Allocator durations include probe call/return overhead; compare like-for-like
  instrumented runs, not raw diagnostic timing against production timing.

The event writer publishes its sequence last. Readers must reread it and reject
zero/changed records. Track snapshots publish an even sequence after an odd
in-progress sequence. Rings overwrite old records, never allocate or print.
These records separate enqueue versus allocation frames and remaining native
release work; no USB stream is opened by the module.
The records are currently collected through emulator memory dumps. This module
has not extended the hardware USB LOAD METER request: `load_meter.py` cannot
read these new buffers yet. Hardware collection needs a separate readout
integration; merely flashing the diagnostic variant does not expose them.

`tools/verify/verify_supersaw_lifecycle.py` compares native and cached conversion
through the corrected ColdFire EMAC library, including fractional words, eight
tracks, collisions, changed pitches, invalid pitches and native fallback. It
also checks diagnostic ring wrap, timer arithmetic, snapshots and instruction
overhead when those symbols are present. Use the repository's corrected Unicorn
build or point `LIBUNICORN_PATH` at an isolated corrected build. The ordinary
Python wheel is not an EMAC oracle. `verify_supersaw_poly.py --burst` exercises
batched input with full native allocation, selective release, retrigger and
unchanged FX; it records diagnostic events when available.

Hardware replay remains separate: capture the exact patch settings; start with
one note, then the same four-note spaced/batched comparison, OFF then LOW. Keep
the existing timing guard, avoid forced hangs, and distinguish production from
diagnostic timing. Only proceed to a bounded real pattern after timing margin
improves. Do not flash or change a device project as part of these source checks.


Two detuned saw oscillators per note, a sine sub and bounded drive, generated entirely
on the ColdFire CPU. **Both FX1 and FX2 remain available.** No DSP synthesis code,
effect ID or bus buffer is allocated. The normal DSP signal path still applies
the track's effects, routing and output mix, as it does for a sample.

Load `FMSYNTH-SUPERSAW.wav` into one FLEX sample slot and select it on the desired
track. Multiple tracks can share that marker slot. Create the silent marker with
`python3 modules/supersaw/marker.py out/AUDIO/FMSYNTH-SUPERSAW.wav`.
Set LFO-page **VOIC to 1–4** for the maximum simultaneous notes on that track.
Each note has two saw oscillators and its own sine sub. Play chords with MIDI/keyboard notes. S7 removes CHRD shapes and native chord
recording; single-note sequencer triggers remain available. No extra track or FX
slot is reserved.

SRC controls are **PTCH, DETU, MORF, CUT, SUB, DRIV**.
SRC SETUP holds **FINE, RES, ENV, DEC, TYPE**; the sixth knob is unused. DETU linearly spreads
the pair to ±1.5625% in frequency (about 27 cents). MORF changes the second saw
from added to subtracted; with zero detune its quarter-cycle offset produces a
pulse at MORF 127. SUB adds a sine one octave below. DRIV adds bounded saturation; zero
bypasses it. AMP supplies the note envelope. The existing Synth Machine owns
MIDI, sequencer, pitch and voice lifecycle; ordinary FM remains selectable.

S8 makes TYPE a native four-position **OFF / LOW / BP / HP** switch, one
position per encoder event including when pressed. Changing VOIC only changes
the available note count: a note keeps its mono level at VOIC 2, 3 and 4.
Chord notes add at their independent AMP levels; the final sum saturates safely
at full scale. Dense, driven or resonant chords can still reach that limit.

## Adaptive CPU path (S9)

Four voices per track, independent AMP releases and per-note filters remain.
No FX slot is reserved. The parameter layout and saved Part format are unchanged.

- The filter now runs at 22.05 kHz **before** four-point interpolation. CUT
  retains its frequency law up to a **9 kHz ceiling**. This changes the sound
  of existing filtered patches, particularly at high cutoff; it is not a
  sample-exact replacement for the historical full-rate filter.
- LOW at CUT=127, RES=0 and ENV=0 is transparent: it fades to bypass, then
  stops filtering. Closing CUT, raising RES or enabling ENV resumes the filter
  with its normal activation fade and a fresh filter envelope.
- TYPE OFF skips filter work after the fade. SUB=0 and DRIV=0 select loops
  with no sub lookup or drive arithmetic. Sub phase still advances, so turning
  SUB back up does not restart it. Silent zero-to-zero AMP blocks skip synthesis;
  audible attacks/releases are still rendered independently.
- Filter decay advances once per block using elapsed sample time, including
  while ENV=0. Its final inaudible tail is discarded when no ENV value can move
  integer CUT. This is an approximation of the old sample-wise decay.
- Drive uses a 16 KiB lookup with a maximum error of **five signed 16-bit PCM
  units** relative to the original cubic, verified exhaustively. DRIV=0 avoids
  this approximation. Filtered interpolation peaks saturate instead of wrapping.
- Fully enabled filters use dedicated LOW/BP/HP coefficient-ramp loops. Normal
  16-sample audio calls need no divisions, including pitch changes and AMP ramps.

S9's linked ColdFire benchmark compares against module main `f6910d5` using
two independent four-note tracks, 16 output samples per call, and 256 measured
blocks after 16 warm-up blocks. These are **executed instructions, not hardware
cycles or whole-device CPU percentages**; caches and bus contention are not modeled.

| Scenario | Before (both tracks) | S9 | Instruction reduction |
| --- | ---: | ---: | ---: |
| Filter OFF, sub/drive enabled | 7358.7 | 6732.7 | 8.5% |
| LOW cutoff sweep | 20860.1 | 12657.4 | 39.3% |
| BP cutoff sweep | 19783.9 | 12372.1 | 37.5% |
| HP cutoff sweep | 19733.6 | 12397.9 | 37.2% |
| Fully open neutral LOW | 16294.0 | 5388.0 | 66.9% |

A four-voice zero-to-zero gain call falls from 11,819 to 525 instructions
(95.6%). This is an active-but-inaudible voice case, not a whole-device idle
measurement. The plain dry mono warm case increases from 738 to 747 instructions;
this change is chiefly for filtered polyphony and avoiding unused processing.
The sampled renderer stack peak is 540 bytes versus 468 before (plus caller/OS
stack outside this probe); the nested filter path uses more stack despite
reusing the output buffer. Hardware stack headroom and cache effects are unmeasured.

S9 validation: `make check` passes all 24 source tests, including the scalar
filter oracles and filtered odd/split-call coverage. The composed `radio-bus`
BUILD=80 image passes scoped common/Supersaw gates and separate project-backed
fixtures for two four-note MIDI tracks, filtered mono/poly transitions, native
filter controls, and live T4 assignment beside T3 with independent releases.
The live-add fixture includes T1/T2/T5 THRU and a T6 kick, but no external THRU
audio or reproduction of unknown MIDI routing. The full unscoped suite was not
run. These checks do not establish hardware timing or resolution of the MKII crash.

Image SHA-256: `fdc09df35e727cdacf27b13095b7f0b962e2886885b430fdf4d2a3d202fa621a`.
The qualified layout aligns hot render/filter functions to 16 bytes. This also
avoids an unrelated BRAIN string-pointer fragment matching the builder's raw
staging-address scan in one intermediate layout. The guard was kept intact;
this is not a general fix to the builder, so other compositions must be checked.

The older S1-S8 measurements below describe their own implementations, not S9.
S9's production response check uses a 22.05 kHz TPT analytical reference instead
of claiming the former full-rate Spectrum response. Hardware timing, cache/bus
costs and the reported physical-device crash still require device validation.

## Implementation and limits

S6 and later follow the op1r Supersaw topology: a fixed pair plus sub per note, limited
here to four voices. It does not redistribute oscillators or stack voices in
a separate unison mode. MORF replaces the earlier MIX control in the same knob
position; existing experimental patches keep their numbers but sound different.
The mathematical band-limited tables, interpolation and amplitude budget remain
our own. The reference is [op1r source](https://github.com/pcppcp/op1r-src/blob/main/synth_sdk/plugins/supersaw/supersaw.c); this is not a sample-exact port.

The original MIT-licensed fixed-point engine is recovered from module-repository
commit `e789014` (import provenance: Octabam `3bd99bca`). It contains no OP-1 code
or tables and makes no claim to replicate that instrument. Fourier tables and
detune ratios are generated mathematically. The Synth bridge pins Tim Hastie's
`poly.s` source hash and applies unique anchors; unselected source stays verbatim.
Sophie is optional legacy compatibility only and is not part of this qualification.

Synthesis runs at 22.05 kHz with four-point interpolation to 44.1 kHz, three output
samples of latency, and state preserved across split calls. Eight 2048-point
harmonic banks (1–128 partials) limit aliasing; the fundamental is clamped below
10.77 kHz. This is not alias-free, particularly after drive. Oscillator controls update per source call without smoothing. Filter coefficients
ramp per source call; enabling/disabling the filter fades over 128 samples. The Synth Machine's voice/machine-change behavior
is inherited, including its documented held REL INF machine-switch limitation.

The loader does not clear `.bss`. Every mutable Supersaw object therefore has an
explicit initializer and is emitted into `.data`; the linked-code gate verifies
all 4,796 initialized bytes in S7 (2,842 in S6; 4,442 in S5). The imported version left those objects uninitialized.

## Historical seven-saw measurements (S1–S5)

The following results belong to the previous seven-saw engine. S6 changes its
sound and cost; its evidence is recorded separately below.

Equal-weight side oscillators are summed before multiplication, preserving every
sample and phase bit. Keeping preparation out of line prevents GCC from moving
cached control products ahead of their cache guard. Isolated ColdFire counts for
16 rich-patch samples improved from 1,378 in the import to 1,282 in S1. The
S2 loop seeds the side sum from its first lane, unrolls accumulation four samples
at a time, and interpolates directly into the destination. It preserves output
and voice-state bits, including odd call boundaries. S3 warm counts were 1,089
for the rich patch and 473 for neutral (S1: 623). These are instruction counts,
not hardware cycles. The linked gate guards against instruction regressions.

**The S4 mono baseline ran eight simultaneous tracks in the full-firmware emulator.**
The real-panel gate sends MIDI notes, presses the track/SRC keys, turns DETU
while all eight notes sound, and restores it. The live parameter and audio both
change, note-offs reach silence, both DSP paths deliver every captured frame,
and both FX slot assignments remain unchanged. Dual Supersaw, sequencer,
Supersaw/FM with SPECTRUM + CHARACTER, and native page checks also pass.

Earlier four/eight-track probes could not borrow main's priority-0 idle task
for injected calls. Those failures remain recorded. A stock priority-1
per-voice worker occupies that idle time; the actual priority-3 panel path
still works. A failed idle-call probe does not establish a physical track limit
or an unresponsive panel. Its purpose is not established as timestretch, and
neither marker TSMODE=0 nor a shorter marker removed the idle-call failure.
S5 reuses the native per-track note cap and stealing policy: a new note at
the cap replaces an older voice, preferring releasing voices. This does not
allocate or steal FX slots. Hardware CPU headroom, audio and controls remain
unverified.

S3 also uses an exact Q4 AMP ramp: the former Q15 accumulator overflowed on a
32-sample full attack. A held-level fast path avoids redundant arithmetic.
The complete rich-patch adapter uses 1,289 warm instructions at steady full
gain (S2: 1,485), or 1,467 while ramping. A wide-arithmetic envelope oracle
covers every call length 0–32, attack, release, held/intermediate/clamped
levels and output bounds. S2 was superseded before its queued audio tests.

S4 replaces linear interpolation with the causal four-point kernel
`(-1, 9, 9, -1) / 16`. It adds two output samples (45 microseconds) of latency
and 32 bytes of voice history. The bounded source keeps interpolation peaks
within +/-27,308. Coherent host FFT probes show 5–7 dB less energy outside the
selected bank harmonics across much of the tested pitch range, with less
high-note attenuation. This includes interpolation images and lookup error,
not only aliasing. Near the internal Nyquist limit the improvement is smaller.
The isolated full adapter costs 1,360 warm instructions for the rich held patch
and 1,538 while ramping (S3: 1,289 / 1,467). The rich oscillator loop uses 1,160 warm instructions (neutral: 537),
still below S1 despite the interpolation improvement. S4 passes the standalone
`make check` and the exact named Inserts image gate, including eight-track
real-panel audio. S3 measurements and failed idle-call receipts remain retained.

## Four-note adapter (S5)

The pinned Synth Machine still owns MIDI and sequencer note allocation, chord
shapes, individual pitches, AMP envelopes and the per-track voice limit. The
Supersaw adapter renders its four native note records using independent
oscillator/resampler histories. Native poly gains retain their equal-power
scaling; the sum saturates safely rather than wrapping if coherent peaks
exceed full scale. One track's notes share that track's controls and effects.

Changing VOIC across a sounding note preserves the native transition: mono
history is copied into the carried voice; poly tails fade under a new mono
note. Warm retriggers preserve phase, cold voices reset. The mono path without
tails keeps S4's samples unchanged. Added mutable storage is 3,200 bytes,
including per-note diagnostic counters, initialized in the runtime image.
Source, cross-architecture arithmetic and carry-hook checks pass. The complete
four-note rich adapter uses 5,692 instructions per 16-sample held block in the
linked ColdFire probe; this is not a hardware cycle or CPU-headroom measurement.
S5 passes the standalone `make check`. All cases pass on the exact named
`SAW INSERTS S5` image: mono regressions, native page, eight-track panel input,
four-note rich chords with SPECTRUM + CHARACTER in the two FX slots, sequencer
chords and mono/poly transitions. The original image driver stopped on disk-full
while staging a fixture; its remaining two cases passed separately on the same
image. The original failed run is retained and is not called clean. An earlier
standalone attempt also failed on disk-full; its complete rerun passed.

Scoped emulator cases pass for two, three and four notes, including independent
note-offs, replacement at the voice cap, silence and retrigger. Two and four simultaneous
rich four-note tracks also pass (up to 16 notes tested successfully). The 32-rich-voice stress case fails later MIDI
note changes even with messages spaced 5 ms apart; do not treat 32 voices as
qualified. Both DSP capture paths remained continuous, and the cause of missed
input is not established. Failed captures and logs are retained.

## Verification

`python3 modules/supersaw/generate.py --check` reproduces tables and assembly.
The host gate uses ASan/UBSan, an independent Fourier reference and 10,000 changing
control blocks against a scalar arithmetic oracle. The linked ColdFire gate
checks boot initialization, 702 exact samples, empty/odd/chunked calls, extreme
pitches, phase wraps and bounded warm instruction counts. The polyphonic wrapper
adds 372 exact host/ColdFire output values, safe coherent-peak mixing and an
actual assembly carry-hook register/history check.
The image gate runs disposable project copies and checks note-off at the source,
separately from effect tails. It also resolves native Supersaw/FM descriptors and exercises actual panel
input while eight voices run. These results do not turn the broader combined
remix suite, which has retained reference-fixture failures, into a clean pass.

Run the gates inside the prepared Octabam worktree; see
[CPU Supersaw integration](../../integration/SUPERSAW.md). Neither a build nor an
emulator pass establishes physical-device acceptance.

## Two-saw engine (S6)

Each of the four notes now has two symmetrically detuned saws and one sub.
MORF replaces MIX and continuously changes the second saw from addition to
subtraction. This follows op1r's fixed per-note topology; it keeps our own
band-limited synthesis and does not claim an exact OP-1 sound match.

The linked four-note rich held block uses 3,900 instructions per 16 output
samples, down from S5's 5,692 (31.5%). Rich single-note synthesis uses 712
instructions (S5: 1,160), and the full-gain mono adapter uses 916 (S5: 1,360).
These are instruction counts, not measured physical CPU headroom. Per-note
history shrank from 96 to 56 bytes; initialized mutable storage is 2,842 bytes.
Independent Fourier checks cover both MORF endpoints; source sanitizer tests
cover changing controls, pitch bounds, split calls and four-note lifecycles.

S6 passes the standalone full check and all scoped exact-image cases: mono
regressions, native labels, eight-track DETU/MORF panel edits, four-note MIDI
with both FX occupied, sequencer chords, live mono/poly transitions and four
rich four-note tracks (16 notes). Both DSP capture paths remain continuous.
The sequence analyzer initially reported an octave error because it counted
zero crossings of the new paired waveform. A full-spectrum peak check confirms
C4; reanalysis passes on the unchanged capture. The original failure remains
retained. The first full check stopped on stale generated docs; the corrected
rerun passed. These are emulator results; hardware remains unverified.

## Per-note SEM filter (S7)

TYPE selects OFF, LOW (LP), BP or HP. CUT is the base cutoff (about 60 Hz–14.4 kHz);
RES adds resonance. ENV opens the filter at each note-on, then DEC returns it
toward CUT (roughly 20 ms–3.5 s to 1%). This is a separate note envelope, not
Spectrum's audio envelope follower. Each voice retains its own filter history,
filter decay and native AMP release. A carried mono note preserves its sweep;
a newly allocated/retriggered note starts its own. Knob settings are shared by
the track. LP/BP/HP selection changes taps immediately.

The filter runs on the CPU at 44.1 kHz before each note's AMP and the voice sum.
It adapts the TPT SEM equations and resonance law from sambanks' SPECTRUM filter
(Zavalishin design; audiojs/filter MIT reference), using Q14 coefficients and
bounded 24-bit states. Both FX slots stay available for processing the mixed
track. TYPE OFF skips sample filtering after a 128-sample bypass fade (2.9 ms),
and settles to the exact previous oscillator/AMP output. It retains a small
branch/state overhead, not the enabled filter cost.

FINE moves from SRC to SETUP. Old experimental Parts migrate FINE once, set CUT
to 127 and leave TYPE OFF. Setup values use a tagged, otherwise unused NEIGHBOR
setup row in a FLEX Part; the actual FLEX LOOP/SLIC/TSTR settings stay intact.
The scoped native-validator wrapper preserves this row during loading. Work on
a copy of an experimental project: stock/older firmware does not understand the
new tagged settings, and old FINE parameter locks now address CUT. Setup filter
controls are per-Part values; only CUT is in the main parameter-lock/LFO lane.

Source sanitizers exercise 100,000 changing filter blocks. The linked ColdFire
gate compares 4,800 exact filter samples with the host implementation, checks
carry history/envelope identity and records enabled/bypassed instruction counts.
The response gate compares the CPU filter with the actual SPECTRUM DSP build:
27 low-level sine probes across cutoff/resonance and LP/BP/HP differ by at most
0.033 dB. This is response agreement, not sample identity or proof of identical
high-level saturation. Its initial low-cutoff precision failure remains recorded;
the corrected 24-bit-state implementation passes.

S7's linked four-note rich held block measures 3,939 instructions with TYPE OFF
(S6: 3,900), and 11,859 with LP and an active filter decay. These are instructions,
not physical cycles or a measured hardware voice limit. Native SETUP encoder
edits and CUT survive SAVE PROJECT and a cold disk reload in the emulator,
including both work/strd files, with FLEX transport settings unchanged.


S7 passes the standalone full check and the exact `SAW INSERTS S7` image cases:
mono/sequencer regressions, mixed Supersaw/FM with both FX occupied, eight-track
DETU/MORF panel edits, four-note MIDI with OFF and LP, filtered mono/poly
transitions, SETUP/CUT encoders, native save/cold reload and page resolution.
Four filtered notes on one track are qualified; no larger filtered-polyphony
claim is made. Four smooth OFF/LP/BP/HP example renders have audible AMP release
and silent endings. The first audio launch stopped before rendering because the
Spectrum reference build replaced shared runtime symbols; the runner now restores
the candidate afterward. Initial failure logs remain beside corrected passes.
These are source/emulator results; physical hardware remains unverified.

## S8 control, level and CPU changes

The S7 native allocator applied `32768/sqrt(VOIC)` to every note, even when
only one note sounded. S8 changes that ceiling only for selected Supersaw
tracks, to 32767, preserving the native attack/release and voice-stealing
lifecycle. Ordinary FM retains its original scaling. An emulator A/B gate
measures the old -3.01/-4.77/-6.02 dB reduction and verifies matched levels for
VOIC 1..4 in S8, then plays 1..4-note chords and verifies their releases.
The same gate drives the TYPE encoder through all four positions, its endpoints
and pressed state, and captures the actual rendered four-position widget.

The CPU audit covers oscillator preparation, interpolation, AMP/mixing,
filter modes and coefficient changes, fine/Part refresh and the inherited
per-track FM parameter preparation. Retained optimizations are:

- One aligned, alias-safe control-word read for the oscillator cache guard.
- Direct accumulation into the polyphonic mix, with shared filter controls.
- Cached unchanged filter coefficients and a generated integer damping table.
- Specialized fully wet filter loops; register-local integrators and envelope.
- Exact Q14 split multiplication with one fewer shift per filter multiply.
- Unrolled six-byte setup refresh and omission of unused poly FM preparation.
- Measured `-O3` generation; sanitizer and linked-arithmetic checks stay enabled.

A scalar S7 filter with independent 64-bit multiplication remains a test oracle.
Randomized modulation and steady OFF/LOW/BP/HP/bypass transitions compare every
sample and state bit. Interpolation, oscillator count, sample rates, filter
response and envelope laws have not been reduced to obtain the savings.

For a 16-sample held block, the expanded ColdFire profile measures four voices:

| Patch | S7 | S8 |
|---|---:|---:|
| Plain, filter OFF | 3,075 | 2,715 |
| Rich, filter OFF | 3,948 | 3,688 |
| Plain, LOW | 10,991 | 8,131 |
| Rich, LOW | 11,868 | 9,108 |
| Rich, BP | 11,667 | 8,791 |
| Rich, HP | 11,731 | 8,859 |

The settled filtered four-note block removes 20 divide instructions.
Fine/Part refresh falls from 117 to 94 instructions, and the isolated native
parameter-preparation span falls from 34 to 11 (including one removed divide).
All 40 profiled mono/poly/mode/patch combinations improve in cold, warm and
cutoff-change calls. Across all 280 probes (also pitch changes, attack, release
and silent tails), 279 improve. The rich mono OFF attack costs four more
instructions, 1,119 to 1,123 (+0.36%); it is retained as the measured tradeoff.
These are executed instruction counts, not physical
cycles, CPU utilization or a new multi-track hardware guarantee. See
`tools/verify/verify_supersaw_cpu.py` for the reproducible profiling fixture.
The existing linked gate separately enforces budgets of 3,800 instructions
filter OFF and 9,400 filtered for its four-note held fixture.


S8 passes the standalone `make check REMIX=supersaw BUILD=S8` (project cases
separate), module source checks (24 tests), and all 11 project-backed cases on
the exact named `SAW INSERTS S8` image: mono/sequencer, mixed FM and occupied FX,
eight-track DETU/MORF panel edits, four-note MIDI, live mono/poly transition,
filter controls, native save/cold reload, VOIC level/TYPE switch and filtered
four-note MIDI. The native descriptor and linked arithmetic gates also pass.
One-note levels at VOIC 1..4 differ by less than 0.003 dB. The rendered native
TYPE widget was visually inspected. Three LOW/BP/HP example captures have
verified releases, silent endings and unused FX slots.

Image SHA-256: `00d68934661a16d503e633b0021499259035eb155ed342db1b05c29eaf9176ad`.
These are source/emulator checks; physical playback and CPU headroom remain
unverified. This does not replace the broader Inserts suite's retained fixture
exceptions or extend the one-track filtered-polyphony qualification.

### VOIC control correction

VOIC advances one position per detent, bounded to 1..4. Its four dial positions
span the full arc (0/42/84/127). An inherited stock SPD3 value such as 32
uses the same effective value of 1 for both the number and dial, without
changing stored settings. Native hidden-value sentinels remain supported.

The compiled gate checks signed detents and 32 drawer/formatter ABI cases.
`verify_supersaw_voic_port.py` checks single steps, endpoints and independent
edits on two tracks. A separate live-assignment fixture checks four distinct
dial positions, adding a second Supersaw while the first plays, four MIDI
notes per track, filter edits and releases.

A reported MKII exception during filter editing with two Supersaws remains
unresolved. Synthetic emulator fixtures have not reproduced it; neither
these UI corrections nor the filter optimization below are a confirmed
hardware crash fix. Physical timing and playback acceptance remain open.

### Filter updates and UI initialization (24 October 2026)

The SEM normalization coefficient is now an exact generated lookup for all
128 cutoff and 128 resonance values (32 KiB read-only data). The 16/32-sample
coefficient ramps use shifts with signed truncation; shorter/split calls keep
the original division. This preserves the existing sound, independent filter
envelopes and OFF bypass. No voice capacity, FX slot or project format changes.
The four-voice, 16-sample cutoff-change probe executes zero divisions instead
of 16. In the rich LOW case, total instructions change from 10,959 to 11,007;
held output changes from 9,108 to 9,124. The removal trades division for a
small instruction-count increase and table reads. Hardware cycle savings
and CPU headroom are unmeasured; cache effects and the rest of the OS are
outside the probe.

SRC and LFO descriptors are built once and then remain unchanged across
tracks. SRC SETUP resolves through the same Synth PLAYBACK descriptor even
when opened first, preserving the correct pitch bounds, formatter and handler.
Persistent conversion of old FINE settings runs on the UI path; the audio
path reads legacy defaults until then without writing the Part or its saved
shadow. Existing tagged settings and save format remain unchanged.
LFO SETUP's PLAYBACK destinations now read PTCH, DETU, MORF, CUT, SUB, DRIV
on Supersaw tracks; other tracks retain their native destination lookup.
The separate LFO naming seam and build-once descriptor pattern were compared
with upstream OCTA303 v7.1. No OCTA303 oscillator or filter code is imported.

Regression checks cover all 16,384 coefficient pairs, signed ramp division,
100,000 modulation blocks against the scalar filter reference, compiled
ColdFire/host agreement, audio-first legacy initialization, SETUP-first page
resolution, stable descriptors, and 24 native LFO formatter calls across two
Supersaw tracks and stock FLEX. Full-image panel/save checks are recorded
separately. These changes do not establish a cause or fix for the reported
hardware exception.

Local verification of this change: author `make check` (24 tests), shared
combined-image checks plus selected Supersaw gates via
`make check-remix REMIX=radio-bus MODULES=SUPERSAW BUILD=79`, and separate
project fixtures for live T4 addition beside T3, four MIDI notes per track,
filter/VOIC edits, independent releases, unchanged FX assignments and native
save/cold reload all pass. Whole-project gates inside the scoped command skip
without `OT_PROJECT`; the full unscoped suite was not run. LFO SETUP's CUT
label was also visually checked in the emulator.
Tested image SHA-256: `7fdef4ae00e63f080612d741650d98db534ba2837b0826d2a84b0dce496b2c7f`.
This source qualification does not include an installation package or flashing.


## S11 native-frame rendering

Native 16-sample calls now interpolate directly into the poly mix or mono
stereo output while applying the native AMP ramp. They avoid writing and
rereading a separate full-rate per-voice buffer. The oscillator/filter body
is specialized for each output layout; bounded source-loop unrolling avoids
register spills. Odd/pending and non-native block sizes retain the staged
renderer. Controls, four voices, independent releases, both FX slots and
persistence are unchanged; no sound-quality reduction is introduced.

Compared with S10, executed ColdFire instructions for a rich 16-sample call:

| Case | S10 | S11 |
|---|---:|---:|
| Mono first attack, OFF | 1,145 | 920 |
| Mono repeated attack, OFF | 1,059 | 834 |
| Four-note first attack, OFF | 4,024 | 3,533 |
| Four-note repeated attack, OFF | 3,688 | 3,197 |
| Four-note held, OFF | 3,397 | 3,130 |
| Four-note first attack, LOW | 8,020 | 7,485 |
| Four-note repeated attack, LOW | 7,664 | 7,129 |
| Four-note held, LOW | 6,217 | 5,890 |

For regular 16-sample calls with no pending odd sample, maximum measured stack
drops from 700 to 692 bytes for mono and 548 to 536 for poly. Separate probes
of split/pending calls and mono-with-poly-tail transitions find maxima of
708 bytes for mono (S10: 700) and 552 for poly (S10: 548). These figures exclude
callers and the OS; no whole-interrupt stack bound is established. These are emulator
instruction/stack measurements, not hardware cycles or a guarantee that the
reported 436.7-us burst fits the hardware frame budget. A smaller shared-body
experiment regressed held dry rendering and was rejected.

Across 320 native-size profile probes, all 280 audible cold, held, control-change,
attack and release cases improve. The 40 zero-to-zero cases retain synthesis
skipping but add 4–20 instructions from adapter dispatch/register setup; a fully
retired poly call moves from 123 to 124. No release is shortened to get savings.

The source oracle compares 20,000 changing blocks against the staged renderer,
including exact stereo/mix samples, oscillator/filter state, AMP rounding and
output guards. `verify_supersaw_equivalence.py --baseline-runtime PATH`
compares frozen S10 and candidate linked binaries over 1,600 mixed native,
odd and split blocks, with changing pitch, controls, modes, gains and carries.
`verify_supersaw_poly.py --mode mixed --tracks 6,7 --burst` exercises one mono
note plus a three-note chord at a cap of four, independent note-offs and
retrigger, matching the hardware workload's allocation pattern. This fixture
uses controlled test settings, not a captured copy of the user's patch.
The separate two-track four-note and transition gates remain applicable.
S10's opt-in diagnostics and hardware-readout limitation remain unchanged.
