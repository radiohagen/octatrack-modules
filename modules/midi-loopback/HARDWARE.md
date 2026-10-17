# Hardware evidence

Measured on one Octatrack MKII by **radiohagen**, 17 October 2026, using the
1.40C-based standalone Loopback/Part State composition with the silent startup
sequence. This is scoped physical evidence, not acceptance of every routing,
persistence, overload or combined-module scenario.

## Measured timing

| Route | Playback added delay: median (observed range) | Recorder-start added delay: one take |
| --- | --- | --- |
| Native baseline | 0 samples | 0 samples |
| Internal | 0.544 ms (0–0.680 ms) | 32 samples / 0.726 ms |
| Direct MIDI OUT → MIDI IN | 0.952 ms (0.726–1.406 ms) | 16 samples / 0.363 ms |

Playback: one 16-second, stereo 44.1 kHz/16-bit MAIN recording per route at
120 BPM. Left is a native audio-track click; right is the same sample on the
target track, triggered natively or by MIDI. The two channels share the capture
clock. Manual recording start therefore cancels in each left/right difference;
no capture-start quantization or separate-file time alignment is needed.
The first four clicks are discarded, leaving 28 measured pairs per route.
There are no missing or unmatched clicks. The native left/right offset is
zero samples and is subtracted from both MIDI measurements.

Recorder start: recorder 2 captures a nonrepeating waveform from audio track 3.
The waveform position at the start of each take is compared with a native
recorder-trigger baseline. QREC is OFF, TRIG is ONE, fades are zero, and the
intended automatic length is 16 steps. Start/end correlations exceed 0.99999999
and alignment drift is zero samples. The native capture is exactly 2 seconds;
the internal and cable captures are 1.932 and 1.829 seconds. The operator may
have stopped transport early. Their start positions remain measurable, but
these takes do not qualify automatic length, end timing or MIDI stop latency.

**Limits:** these are light-load measurements while internally recording,
before physical output conversion. One recorder start per route cannot rank
internal versus cable timing or characterize jitter. The sample does not
establish a universal sub-millisecond limit: the cable playback take exceeds
1 ms. Repeated runs, busy arrangements and other units remain unmeasured.
External synth response and physical input recording are separate paths.

## Startup and image identity

The tested composition starts quickly after installation and after at least
five minutes powered off, with continued successful use reported afterwards.
These are user observations, not an automated or instrumented reliability test.
The silent DSP-upload entry sequence is retained because removing it can
restore the cold-start stall on this unit. Its cause is unresolved; this is
an observed workaround rather than a general DSP-initialization fix.

- Tested MAIN_OS SHA-256: `d75bfa674e02f1ed1a8736c9884330d70d29803396a445736932982d4473041d`.
- Tested BIN SHA-256: `63e4fb7f008977eb561f055b255fad4252764e88b709b145995460ef2b223943`.
- Linked runtime SHA-256: `812b0b3f7fcebc0a250a56a2b35004518f8dcec9817c15abc7c05ddd628baa6a`.

Image hashes identify the tested artifact without publishing firmware or
requiring knowledge of local package names. Source/layout changes need a new
image comparison; matching source modules alone is insufficient to transfer
cold-start acceptance to another composition.

The machine-readable [measurement receipt](hardware.json) includes raw event
offsets, sample counts, capture hashes and limitations. Raw WAVs are retained
locally; no firmware, device project or audio is distributed in this repository.

## Repeating the measurement

Use three otherwise identical patterns: native target trigger, internal MIDI
target trigger, and direct DIN loopback target trigger. Keep the audio target,
sample, tempo, effects, recorder configuration and load the same. Internal
MIDI must use a dedicated audio receive channel with note reception enabled.
Disconnect the DIN return for native/internal runs. Preserve stereo raw WAVs,
save each capture before overwriting its buffer, and alternate route order.

For playback, capture stereo MAIN in an unused recorder: native reference
hard left, target hard right, clicks every 0.5 seconds. Check a native baseline,
then subtract its channel offset; swap pans and repeat as a cross-check.
For recorder start, capture a nonrepeating reference waveform, compare its
position with native recording, and save the recorder under test rather than
the track's assigned playback sample. On MKII, select that audio track, then
REC1 + BANK opens its recorder buffer; FUNC + REC3 offers SAVE THIS RECORDING.
The MIDI takes should be allowed to finish before stopping transport.

Octabam's `tools/hw/measure_midi_loopback_latency.py` analyzes the WAVs with
Python's standard library. Supply the native baseline first. The recorder
mode also needs the exact original probe WAV. Repeat enough starts to study
variation; preserve rejected/empty takes rather than counting them as passes.
