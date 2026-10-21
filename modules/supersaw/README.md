# Supersaw

Seven detuned saw oscillators, a sine sub and bounded drive, generated entirely
on the ColdFire CPU. **Both FX1 and FX2 remain available.** No DSP synthesis code,
effect ID or bus buffer is allocated. The normal DSP signal path still applies
the track's effects, routing and output mix, as it does for a sample.

Load `FMSYNTH-SUPERSAW.wav` into one FLEX sample slot and select it on the desired
track. Multiple tracks can share that marker slot. Create the silent marker with
`python3 modules/supersaw/marker.py out/AUDIO/FMSYNTH-SUPERSAW.wav`.
Set LFO-page **VOIC to 1–4** for the maximum simultaneous notes on that track.
Each note has seven saw oscillators and its own sine sub. For keyboard/MIDI
chords set **CHRD to ----**; a chord shape instead generates a chord from each
trigger, including sequencer trigs. No extra track or FX slot is reserved.

PLAYBACK controls are PTCH, DETU, MIX, FINE, SUB and DRIV. DETU reaches ±35 cents
with a quadratic response. MIX balances the centre oscillator and six detuned
sides. SUB adds a sine one octave below. DRIV adds bounded saturation; zero
bypasses it. AMP supplies the note envelope. The existing Synth Machine owns
MIDI, sequencer, pitch and voice lifecycle; ordinary FM remains selectable.

## Implementation and limits

The original MIT-licensed fixed-point engine is recovered from module-repository
commit `e789014` (import provenance: Octabam `3bd99bca`). It contains no OP-1 code
or tables and makes no claim to replicate that instrument. Fourier tables and
detune ratios are generated mathematically. The Synth bridge pins Tim Hastie's
`poly.s` source hash and applies unique anchors; unselected source stays verbatim.
Sophie is optional legacy compatibility only and is not part of this qualification.

Synthesis runs at 22.05 kHz with four-point interpolation to 44.1 kHz, three output
samples of latency, and state preserved across split calls. Eight 2048-point
harmonic banks (1–128 partials) limit aliasing; the fundamental is clamped below
10.77 kHz. This is not alias-free, particularly after drive. Controls update per
source call without smoothing. The Synth Machine's voice/machine-change behavior
is inherited, including its documented held REL INF machine-switch limitation.

The loader does not clear `.bss`. Every mutable Supersaw object therefore has an
explicit initializer and is emitted into `.data`; the linked-code gate verifies
all 4,442 initialized bytes. The imported version left those objects uninitialized.
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
