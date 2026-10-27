# Sophie FUSE proof of concept

Experimental mono FUSE voice from [Digisophie](https://github.com/soejrd/digisophie), pinned as an unmodified MIT-licensed submodule. Uses the existing Synth Machine source transport and AMP envelope; no DSP code, effect ID, shared bus buffer or battery SRAM allocation.

Load `FMSYNTH-SOPHIE.wav` on a FLEX track. Set VOIC to 1. Create the silent marker with `python3 modules/sophie/marker.py out/AUDIO/FMSYNTH-SOPHIE.wav` (the script refuses to overwrite an existing file). PLAYBACK controls: PTCH, COLR, METL, FINE, FBK, SWEP. SWEP 64 is neutral, lower values sweep upward and higher values downward toward the note. AMP shapes the note. FOLD is bypassed; BOOM/PIPE/SHARD and polyphony are outside this POC. Unsupported polyphonic playback is silent rather than falling through to the FM engine. Ordinary FMSYNTH markers retain the existing FM engine.

The engine keeps its 48 kHz output and internal 24 kHz oscillator cadence; the adapter resamples to 44.1 kHz and ramps the existing AMP gain across split source blocks. Its resampling step carries the pitch fraction lost by the engine's integer phase increment, so adjacent positive and negative FINE cents can affect the output even at low notes. The adapter adds 6 dB to the engine's conditioned output before the normal AMP and mixer stages; in a host render, a sustained FUSE patch peaks at -6 dBFS at unity AMP instead of -12 dBFS. Controls reach the next 32-frame engine block. The optional bridge hash-checks the pinned Synth source and inserts explicit callbacks without editing that submodule. It owns no second copy of a stock hook. Without SOPHIE selected, the bridge emits the original assembly verbatim.

Build `make bus REMIX=sophie`. Generate the assembly with `python3 modules/sophie/generate.py`.
## Measured locally

- The host adapter matches an independently resampled render of the pinned upstream engine exactly. Irregular source block splits, marker isolation and unsupported polyphony are checked.
- Full firmware: Sophie on T2 alongside FM on T6 with native MIDI; Sophie on T6 alongside FM on T2 with sequencer notes; metallic Sophie over MIDI Loopback. Each checks release, both bus hosts and actual DSP-facing FX2 IDs. The first two also play and release a concurrent Harmony chord.
- The normal FM engine retains three-note chords and note releases on both cores.
- The installed native page resolver selects separate Sophie and FM descriptors with the correct labels.
- Both DSP payloads are byte-identical to OCTABAM84. The complete remix selection is retained, with one module added.
- Building the standard `mattias-bottleservice` remix with `BUILD=84` from this tree reproduces the original OCTABAM84 MAIN OS byte for byte (SHA-256 `d3fb346482a043888879c01d3dfe546fab12e30c07b1a57d15b83fb3467f2d22`).

The full remix gate result and exact image identity are recorded in the local POC receipt. The unrestricted `make check` was stopped when the Kits save-project scenario stalled; a standalone run of that scenario on the unchanged standard firmware also exceeded a 180-second limit. The broad suite is therefore incomplete. `make check REMIX=sophie BUILD=S1 MODULES=SOPHIE` with the hosted fixture passed with no failures or skips, including the shared boot/menu/set/USB floor and the Sophie image gate. This does not claim that the Kits gate passed. These are emulator results, not physical hardware timing or audio qualification. Only one mono Sophie track at a time is qualified by this POC; no eight-track capacity is claimed. Parameter automation and live marker/machine changes need further qualification. Existing standard-remix hardware limitations still apply.

Verification commands (after building the combined remix):

```sh
python3 tools/verify/verify_sophie.py
.venv/bin/python3 tools/verify/verify_sophie_port.py --project out/release-fixtures/base --track 2
.venv/bin/python3 tools/verify/verify_sophie_port.py --project out/release-fixtures/base --track 6 --case sequence
.venv/bin/python3 tools/verify/verify_sophie_port.py --project out/release-fixtures/base --case loopback --metal 96
```

The page verifier uses the frozen candidate and T2 fixture from the preceding runs. No card copy or firmware flash is part of these checks.

In a Sophie-enabled Octabam integration, `make check REMIX=sophie` runs the
host gate and, with `OT_PROJECT` set, the Sophie image gate. This source
repository's `make check` only validates the published source and metadata.

## CPU profile (25 October 2026)

The adapter caches pitch conversion until PTCH/FINE changes and replaces its
per-output-sample division by 147 with a Q16 interpolation table. The generated
ColdFire source now uses `-O3`. The pinned Digisophie engine and FUSE controls
are unchanged. Against the previous adapter, a 44,100-frame host render differs
by at most 2 PCM units after the 6 dB output gain (0.223 PCM RMS). Exhaustive
interpolation checks bound the pre-gain error to 1 PCM unit.

The standalone ColdFire profile reports 3,840 to 3,644 executed instructions
per 16-frame metallic call, and 19.25 to 2.25 long divisions on average. Two
active Sophie tracks total 7,681 to 7,288 instructions and 38.5 to 4.5 long
divisions per 16-frame pair. Instruction counts do not capture division
latency, and hardware cycles have not been measured. Linked adapter text and
tables grow from 7,964 to 9,484 bytes; the composed image builds within its
placement.
Run `tools/verify/verify_sophie_cpu.py` with Python's Unicorn package and the
ColdFire toolchain to reproduce the instruction counts. Its JSON receipt is
written under ignored `out/`.

## Further CPU optimization (26 October 2026)

This pass keeps the previous optimized adapter's samples and state exactly.
The resampler cursor stays in local variables during each source call, and a
settled unity AMP gain avoids redundant multiplication. The pinned engine
always writes PCM with a zero low word, allowing an exact signed shift when
reading its output. A small compiler-specialized wrapper exposes the existing
FUSE, full-velocity and 32-frame constants to GCC; upstream source and its
24 kHz oscillator / 48 kHz output cadence remain unchanged.

Compared with module `fde8036` (which includes the 25 October optimization),
the direct ColdFire renderer profile measures these instructions per 16 frames:

| Workload | Before | After | Reduction |
| --- | ---: | ---: | ---: |
| Plain FUSE, unity AMP | 3,592.94 | 2,863.19 | 20.3% |
| Metallic FUSE, unity AMP | 3,643.75 | 2,911.38 | 20.1% |
| Metallic FUSE, pitch sweep | 3,671.69 | 2,951.63 | 19.6% |
| Two metallic tracks, total | 7,287.50 | 5,822.75 | 20.1% |
| Partial gain, attack or release | 3,643.75 | 3,114.75 | 14.5% |

Linked standalone text/constants grow from 9,484 to 11,172 bytes; BSS stays
at 2,444 bytes. Measured peak stack in the stateful comparison grows from
176 to 180 bytes. These are executed instruction counts from direct calls
to the renderer, not hardware CPU percentages, timing or a track-capacity claim.
The code-size tradeoff still needs physical cache/timing measurement.

The host regression compares 64,512 specialized blocks with the unchanged
generic upstream renderer, checking exact PCM, every engine-state byte,
parameter immutability and the zero-low-word invariant. `make check` now runs
this adapter regression with address and undefined-behavior sanitizers.

The reusable CPU verifier also compares baseline and candidate ColdFire code
through live controls, pitch/clamp boundaries, FINE increments, retriggers,
marker changes, gain ramps, all eight independent state slots, unsupported
polyphony and every call length from 0 through 32. It checks output guards,
callee-saved registers, stack balance, counters and complete existing voice
state. Its eight-slot probe does not establish real-time eight-track capacity.

```sh
python3 tools/verify/verify_sophie_cpu.py --baseline-ref fde8036 --output out/sophie-cpu.json
# Use the Octabam integration's Python with Unicorn; optionally pass its
# final out/platform/runtime/runtime.elf through --elf for linked-code checks.
```

Receipts pin the baseline source, assembly, linked ELF and verifier hashes.
The generated assembly is checked with `python3 modules/sophie/generate.py --check`.
