# Euclid LFO implementation decisions

This fixed-step revision supersedes the original bar-fitted prototype.
Evidence is image-specific; no physical-device acceptance or card installation
is claimed. Historical local prototypes are not part of this source release.

## Fixed-step timing revision (22 October 2026)

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

## Final software acceptance

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
