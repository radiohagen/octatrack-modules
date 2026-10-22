# Timing and verification

The display reports **nominal full-cycle duration**. Native fixed-point
rounding, retrigger modes, scenes and modulation can affect the audible
cycle; no engine arithmetic is patched.

## LFO scale

Both audio and MIDI use `512 / (SPD * 2^MULT)` quarter notes for the nominal
cycle. SPD zero is stationary. The draft used 1024; that was rejected by
separate probes of both native firmware paths before delivery.

Audio: the stock loop at `0x40003b90` (also inlined at `0x4000cf40`) reads
SPD in Q8.8, tempo24 times four, and the MULT shift. It advances the
23-bit phase once per 16-sample frame. Its fractional MAC reciprocal is
8657. Native-port phase measurements cover five SPD/MULT/tempo settings;
the verifier allows the stock reciprocal and integer quantization error.
The stock remainder path is not treated as an exact rational clock.

MIDI: `0x40003df8` advances phase by approximately `SPD * 512 / 3`, shifted
by MULT, per fine update. At 120 BPM the actual sequencer calls it 192 times
per second: 96 updates per quarter note. Its reciprocal divide can round
one unit up; the phase gate permits only that quantization. The coarse-tick
argument multiplies the increment by four; the normal internal-clock
measurement sees the fine path. External-clock behavior has not been
physically measured.

The earlier standalone Unicorn audio probe used an unpatched EMAC engine
and is not evidence. The timing verifier uses this worktree's native port.
All display-only unit checks use integer instructions and do not depend
on Unicorn's EMAC support.

## Echo Freeze

SYNC on uses `(raw + 1) / 32` quarter notes. The stock delay buffer clamps
to 176400 samples (four seconds at 44.1 kHz); longer requests show `4s`.
The sync-off conversion is intentionally deferred. Custom DELAY SERVER /
TEMPO SYNC formatting is independent and is not registered over.

## Additional parameter mappings

- MIDI LEN/NLEN: `raw / 24` quarter notes for raw 1..126. The stock
  scheduler at `0x4009fd58..6c` stores `raw * 4` fine ticks, with 96 fine
  ticks per quarter. The linked-code gate executes that assignment for
  every raw value, including the high end where the native text table has
  misleading fractions. Native zero and infinity remain `0` and `INF`.
- ARP SPD: `(raw + 1) / 24` quarter notes, raw 0..95. The official manual's
  six-clock sixteenth-note definition agrees with the native formatter's
  `raw + 1`. TRAN remains `raw - 64` chromatic semitones, now suffixed `st`.
- Recorder FIN/FOUT: stock `0x400ab63a` contains `992250 * L`; duration is
  `L / 64` quarter notes. The gate independently builds the step ladder and
  compares every stock entry. The sample arithmetic and tempo reciprocal
  are documented in `docs/firmware/RECORDER.md`; this changes neither.
- Static/Flex RTIM: the engine at `0x40004084..b8` interpolates the table
  `0x400aae0c` using the Q8 parameter at frame offset 10. At integer raw
  settings its entry is at `base + raw * 16`. Entries divided by 1016064000
  give quarter notes, matching `2^((raw - 91) / 12) / 4`. The counter
  advances by `tempo24 << 4` per sample (`0x4000405e..66`, executed by the
  linked-code gate), so the native decimal display counts sixteenth-note
  sequencer steps. A draft denominator of 63504000 was rejected before
  delivery: it overlooked that shift and overstated RTIM by sixteen. The gate verifies
  all 128 entries against that independent formula (less than one table
  unit of rounding). Powers of two at `7 + 12*k` use exact musical names;
  intermediate settings use the actual engine table and live tempo.
  Quotient/remainder conversion avoids overflow at the slowest tempo.

These are nominal parameter durations. Modulation, scene interpolation,
legato, retriggers, sample endings and track modes can change the resulting
sound or MIDI events. Only LFO phase/tick timing has an independent running
native-port timing probe; the added mappings have stock-code/table evidence,
exhaustive linked-code checks and native panel captures.

## Reproduce

1. `make check REMIX=musical-units`
2. `.venv/bin/python tools/site/capture_manual.py musical-units --project <disposable source>`
3. `.venv/bin/python tools/verify/verify_musical_units_port.py`

Capture preparation copies the source. Screenshots come from actual panel
UART bytes, with firmware hashes in `docs/site/screenshots.json`. The timing
step writes `out/manual-captures/musical-units/timing.json`. The linked-code
gate records `out/musical-units/formatters.json` for its exact image.

Checks include all raw SPD/MULT combinations, every track/Part/LFO context,
all delay values with both SYNC states, all new parameter values at six
tempos, native MIDI counter assignments, carry boundaries, all
callee-saved registers, guarded six-byte buffers, native text widths, and
writes restricted to the stack/output. They do not prove physical hardware
acceptance or live modulated-period measurement.

## Held-lock pixels

Stock's highlighted dial inverts 17 columns, while its centered text can
span 19. Labels such as `123ms` then cross the highlight edge. The module's
widget wrappers delegate the complete dial or numeric cell to stock and extend
that highlight by one column on each side. Only the seventeen adapted slots use them.
The capture checks every label pixel against the normal `123ms` image: all
19 columns invert, and the neighboring depth cells remain identical. A second
pixel assertion checks the numeric MIDI LEN cell against its normal `146ms`
label. The capture verifies the Part bytes after native encoder edits, since
normal and held-lock MIDI editing use different encoder resolutions.

The expanded fixture produces 18 panel captures. The linked-code gate makes
21,000 formatter calls and checks 1,324 distinct labels at native font width.
