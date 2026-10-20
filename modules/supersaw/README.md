# Supersaw

Seven detuned saw oscillators, a sine sub and bounded drive, generated entirely
on the ColdFire CPU. **Both FX1 and FX2 remain available.** No DSP synthesis code,
effect ID or bus buffer is allocated. The normal DSP signal path still applies
the track's effects, routing and output mix, as it does for a sample.

Load `FMSYNTH-SUPERSAW.wav` into one FLEX sample slot and select it on the desired
track. Multiple tracks can share that marker slot. Create the silent marker with
`python3 modules/supersaw/marker.py out/AUDIO/FMSYNTH-SUPERSAW.wav`.
Set LFO-page **VOIC to 1**: seven oscillators form one note, not seven MIDI voices.
VOIC 2–4 is unsupported and silent. No extra track is reserved or stolen.

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

Synthesis runs at 22.05 kHz with linear interpolation to 44.1 kHz, one output
sample of latency, and state preserved across split calls. Eight 2048-point
harmonic banks (1–128 partials) limit aliasing; the fundamental is clamped below
10.77 kHz. This is not alias-free, particularly after drive. Controls update per
source call without smoothing. The Synth Machine's voice/machine-change behavior
is inherited, including its documented held REL INF machine-switch limitation.

The loader does not clear `.bss`. Every mutable Supersaw object therefore has an
explicit initializer and is emitted into `.data`; the linked-code gate verifies
all 1,210 initialized bytes. The imported version left those objects uninitialized.
Equal-weight side oscillators are summed before multiplication, preserving every
sample and phase bit. Keeping preparation out of line prevents GCC from moving
cached control products ahead of their cache guard. Isolated ColdFire counts for
16 rich-patch samples improved from 1,378 in the import to 1,282 in S1. The
S2 loop seeds the side sum from its first lane, unrolls accumulation four samples
at a time, and interpolates directly into the destination. It preserves output
and voice-state bits, including odd call boundaries. Warm counts are now 1,089
for the rich patch and 473 for neutral (S1: 623). These are instruction counts,
not hardware cycles. The linked gate guards against instruction regressions.

**S1 qualification is limited to two simultaneous synth tracks.** Its full-firmware
emulator checks cover dual Supersaw and Supersaw/FM, source release, sequencer
playback, both DSP output paths, and two occupied stock effect slots. Four- and
eight-track stress probes starved the emulator main task at the frame-500 UI
call; their failing evidence is retained. There is no automatic voice stealing
or imposed track cap. S2 was superseded before its queued audio tests started. S3 adds an exact
Q4 AMP ramp (the former Q15 accumulator overflowed on a 32-sample full attack)
and a held-level fast path. At steady full gain, the complete rich-patch adapter
uses 1,289 warm instructions instead of S2's 1,485; a ramp uses 1,467 instead
of 1,485. A wide-arithmetic envelope oracle covers every call length 0–32,
attack, release, held/intermediate/clamped levels and output bounds.
S3 full-firmware qualification is pending; source and linked ColdFire checks pass. Physical CPU headroom, audio and controls
remain unverified.

## Verification

`python3 modules/supersaw/generate.py --check` reproduces tables and assembly.
The host gate uses ASan/UBSan, an independent Fourier reference and 10,000 changing
control blocks against a scalar arithmetic oracle. The linked ColdFire gate
checks boot initialization, 702 exact samples, empty/odd/chunked calls, extreme
pitches, phase wraps and bounded warm instruction counts.
The image gate runs disposable project copies and checks note-off at the source,
separately from effect tails. It also resolves native Supersaw/FM descriptors.

Run the gates inside the prepared Octabam worktree; see
[CPU Supersaw integration](../../integration/SUPERSAW.md). Neither a build nor an
emulator pass establishes physical-device acceptance.
