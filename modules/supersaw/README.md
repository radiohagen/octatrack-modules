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

## Implementation and limits

S6/S7 follow the op1r Supersaw topology: a fixed pair plus sub per note, limited
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

TYPE selects OFF, LP, BP or HP. CUT is the base cutoff (about 60 Hz–14.4 kHz);
RES adds resonance. ENV opens the filter at each note-on, then DEC returns it
toward CUT (roughly 20 ms–4 s to 1%). This is a separate note envelope, not
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
