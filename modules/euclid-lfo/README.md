# Euclid LFO

Independent ColdFire modulation for all three LFOs on all eight audio and MIDI
tracks. Implemented and emulator-tested; no hardware acceptance or deployment.
The [decision log](DECISIONS.md) records design choices, verification evidence
and the hardware/persistence limits.

Select **EUCL** (Euclid) as WAVE on any audio or MIDI LFO. Native PMTR, SPD, MULT,
TRIG and DEP remain available. It takes no FX slot and does not require the
EUCLID filter/amp effect.

With that lane selected in LFO SETUP, YES opens the pattern editor. YES or
LEFT/RIGHT switches its two pages; NO returns to native setup. The editor is
pinned to the track, Part and lane selected when it opens.

Page 1, encoders A–F: STPS, PULS, ROT, ACNT, AROT, BST (accent boost).
Page 2: OUT, ATK/EDGE/SLEW, DEC/LEN, SWNG, DIR, RATE. LEVEL does nothing. DEC is inactive
for RAND/LOOP. Controls clamp at their limits and encoder pushes do not
accelerate them. The left preview shows rests (`.`), pulses (`o`), and accents (`*`).
The default candidate follows native LFO SETUP's split pane. The development
probe also renders a full-width six-control alternative for comparison;
it is not another saved setting or a hidden panel gesture.

One LFO cycle is one pattern, and **RATE sets each step's duration**, not a
division of a fixed bar. At RATE 1/16, seven steps take seven sixteenths:
0.875 seconds at 120 BPM. The pattern runs across bar lines unless native
TRIG/SYNC modes restart it. Changing STPS changes the cycle length, not the
underlying step duration. Accents add depth to existing pulses; BOOST 127
doubles their modulation amount. Leave headroom in DEP and the destination's
base value to hear that difference. DIR selects POS (raise the destination)
or NEG (lower it); native DEP remains the unsigned modulation amount.

STPS is 1–16; PULS is 0–STPS (zero is silent), with ROT shifting the pattern.
Try 3/8, 5/12 or 5/16; 4/16 gives an even pulse train. ACNT distributes accents
over the existing pulses, AROT shifts that accent sequence, and BST sets the
additional amount. Accents never add extra pulses. SWNG 50 is straight; 80
delays alternate steps. Odd-length patterns restart that alternation each cycle.

OUT chooses ENV (attack/decay), GATE (edge/length), RAND (a new random value
per pulse) or LOOP (the captured random values repeat). SLEW smooths RAND/LOOP
changes. RATE is a shortcut for native SPD/MULT, from whole notes to 1/64
and their triplets (`16T` means a sixteenth-note triplet). Saved native SPD
is 0–127; reverse runtime increments from modulation are still supported.
Custom native speeds display VAR; zero displays STOP, and turning RATE
from STOP selects 1/16. Native SPD/MULT can still be edited normally, and
selecting EUCL does not overwrite them. No extra rate field is persisted.
SPD 64 + MULT 2x gives 1/16; SPD 64 + MULT 1x gives 1/8.
The audio clock uses exact tempo/SPD/MULT arithmetic with fractional carry;
MIDI scales its native tick increment by 16/STPS. Both feed stock cycle handling.
TRIG restarts the whole pattern,
HOLD retains its native latch behavior, and FREE continues while stopped.
ONE plays one complete pattern; HALF plays half a pattern (3.5 steps at STPS 7).
Both end at zero modulation. SYNC variants retain native reset events.

This supersedes the unpublished bar-fitted prototype: existing development
settings with fewer than 16 steps now run proportionally shorter cycles.
Sidecar bytes and native project formats are unchanged; this is an intentional
timing change, not a claim of sound-compatible migration of those prototypes.

This initial module cannot be combined with **PLOCKS P2**: their retained SRAM
allocations overlap, and the build refuses the combination. Native project
file formats are unchanged: WAVE selection uses the native Part field, while
additional settings use versioned `eulfNN.work/.strd` sidecars.

## Development checks

```sh
python3 modules/euclid-lfo/generate_control.py
make bus REMIX=euclid-lfo
python3 tools/verify/verify_euclid_lfo.py
python3 tools/verify/verify_euclid_lfo_card.py --project PATH_TO_TEST_PROJECT
python3 tools/verify/verify_euclid_lfo_ui.py --project PATH_TO_TEST_PROJECT
python3 tools/verify/verify_euclid_lfo_load.py --project PATH_TO_TEST_PROJECT
python3 tools/verify/verify_euclid_lfo_audio.py --project PATH_TO_TEST_PROJECT
```

The focused check runs mathematical boundary/count tests with sanitizers,
checks sidecar byte order, CRC and refusal of malformed data (including
ColdFire codec execution), fault-injects the STORE client lifecycle, tests
the installed Part Save/Clear callbacks, Part Reload copy adapter and native
Part clipboard capture/paste/undo routines (including cross-bank snapshots),
executes the installed ColdFire handlers against a native C reference across
48 lanes, compares complete native trigger consumers against an independent
exact audio-clock oracle and stock MIDI across all eight TRIG modes, and checks
HOLD/terminal behavior, register preservation and native
encoder dispatch, and renders
the editor using the firmware's actual fonts and knob widgets. Both layouts
are rendered at minimum/maximum values in every mode for audio and MIDI,
with checks against framebuffer overflow and edits from inactive controls.
Its receipt, original pixels and enlarged previews are under
`out/euclid-lfo/`. These are software checks, not hardware acceptance or a full
release gate.

The exact audio-clock revision fixes the small accumulating timing error found
in the earlier audio renders; it does not alter stock LFO waveforms. It also
does not make this module identical to the original EUCLID effect: this LFO
uses SPD/MULT rather than the track's speed/swing mask, and the destination's
native gain/parameter curve determines the audible envelope shape.

The panel check boots a copied project, selects EUCLID using the native WAVE
encoder, opens the editor, edits all six pattern controls one count each and
changes pages, for both audio and MIDI. It checks settings and captures the
whole LCD, including native sidebars. It does not poke settings or call the
editor directly; page two also tests DIR and pushed RATE with single counts.
All thirteen RATE presets and leaving STOP are checked on audio/MIDI through
the panel, including the native Part and SRAM mirrors. Rapid 15 ms
encoder bursts, with and without a held push, test exact accumulated counts.
Panel Part save/reload/copy/paste/undo/clear/switch cases check both audio and
MIDI settings and all untouched lanes. `--panel-model mki` exercises the MKI
panel mapping; the default is MKII. The two candidate layouts also have deterministic native
window pixel regressions in `ui-pixels.json`; inspect changed renders before
updating this file, rather than accepting a new hash without visual review.
Additional cases capture native SETUP with EUCL selected and compare FREE's
phase after two stopped intervals, without pressing PLAY or poking settings.

The card check copies the supplied test project into a fresh isolated fixture,
boots the composed image through the native FAT/project loader, drives SAVE
PROJECT through panel input, and checks working/stored sidecars and a fresh
reload. It also checks missing, empty, future-version, short, long and bad-CRC
files. Native WAVE 19 and SPD/MULT are checked in all working/saved Parts through
validation, save and fresh load. It also simulates power-up with unsaved audio/MIDI edits, missing SRAM
state and a damaged retained record. The initial parameter edit is seeded,
not an editor gesture. Separate native refusal-prompt cases drive IGNORE,
OVERWRITE and BACKUP through panel input and verify preserved original/backup
bytes. Original
project files are not modified. Each run retains its own logs, card and receipt
under `out/euclid-lfo-card/`.

The load check creates a deterministic looping FLEX fixture, stages its sample,
and compares stock SQR with 48 EUCLID lanes on the same image. It requires eight
non-silent track chains and main output, includes a native Part change, and
reports ColdFire instruction counts. These are software-model observations,
not hardware-cycle limits or a headroom guarantee for arbitrary remixes.

The audio comparison check renders seven eight-second native main-output
captures: sustained chord, zero pulses, regular 4/16, Euclidean 5/16,
5/16 with two accents, and static/modulated native FILTER. It verifies audible
onset timing, unchanged non-accent hits, stronger accent hits, zero-pulse
silence, output differences and absence of sample clipping. Stereo 24-bit WAV
previews share one gain; raw eight-channel captures are retained. Settings are
seeded before transport, not entered through panel gestures. Outputs and the
exact-image receipt are under `out/euclid-lfo-audio/`. This does not test an
external MIDI instrument or physical audio output.

Add `--showcase` to render the seven-step listening demo: seven sixteenths per
cycle at 120 BPM, four bars each of 1/7, 2/7, 3/7, accented 3/7, accented 5/7 and
accented 7/7. The 50-second montage includes a one-bar count-in and a
post-mixed quarter-note reference click, with separate music/click stems and
six individual eight-second clips. These generated audio files are local
listening artifacts, not firmware or source-repository assets.
The click is a listening aid, not an additional firmware feature. Native
audio onset checks establish 125 ms steps and 875 ms cycles, including their
movement across bar lines; one common gain preserves the accent comparisons.
Two native cycles of pre-roll are discarded before the listening montage.

The current file writer follows STORE's existing buffered-write/close pattern.
It checks both results and retains pending work on failure; this is not an
atomic FAT replacement or a guarantee against power loss during a card write.
Refused files stay protected until the user chooses OVERWRITE or BACKUP.
BACKUP must succeed before a write is attempted, and retries retain that backup.

Rhythm distribution, random generation and envelope curves are independently
adapted from repeat98's EUCLID module in this repository; its effect and source
remain unchanged.
