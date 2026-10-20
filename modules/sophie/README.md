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

`make check` runs the host gate and, with `OT_PROJECT` set, the complete Sophie image gate above.
