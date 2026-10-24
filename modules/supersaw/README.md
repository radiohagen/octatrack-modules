# Supersaw

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
