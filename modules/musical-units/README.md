# MUSICAL UNITS

Shows timing controls in musical notation and arpeggiator transpose in semitones.
An exact division reads `1/16`; `.` means dotted and `T` means triplet.
Between divisions, the display uses milliseconds or seconds, such as `123ms`
or `4.06s`. Zero LFO speed reads `STOP`.

| Area | Converted controls |
|---|---|
| Audio and MIDI LFO | SPD1–3 and SETUP SPD, including MULT |
| Echo Freeze | TIME with SYNC on |
| MIDI NOTE | LEN |
| Arpeggiator | SPD, NLEN, and TRAN in semitones (`12st`, `-7st`) |
| Static and Flex sampling | RTIM, the interval between retriggers |
| Track recorder | FIN and FOUT fade durations |

MIDI LEN/NLEN retain native `0` and `INF`. A zero recorder fade reads `0ms`.
At 120 BPM, MIDI LEN 6 becomes `1/16`, LEN 7 becomes `146ms`; RTIM's native
`1.0` becomes `1/16`, and the next setting becomes `132ms`. The recorder's
native one-step fade becomes `1/16`.

Only the display changes. Turning an encoder still reaches every original
value; parameter locks, scenes, MIDI, saved projects and the sound engine keep
their original values. Increasing LFO SPD still makes the cycle shorter.

Audio and MIDI LFO MAIN and SETUP use the same notation. The displayed cycle
includes MULT. It describes a complete nominal cycle at the selected speed,
not the time until a retrigger or the instantaneous speed under modulation.
HOLD, ONE and HALF retain their native behavior. Milliseconds/seconds use the
current engine tempo; rounded text may repeat on adjacent settings.

Echo Freeze TIME uses musical notation when SYNC is on. Values exceeding the
four-second delay buffer display `4s`. SYNC off retains the original TIME
number; its physical conversion is outside this module's initial scope.

Parameters without a verified physical mapping keep their native display:
AMP attack/hold/release, filter frequencies, effect gains and arbitrary MIDI
CCs. Sample STRT/LEN depend on machine/setup context; they are not assigned
milliseconds from the raw number alone. Recorder RLEN/QREC/QPL and custom
module displays retain their existing meaning and integrations.

## Integration

Select `MUSICAL UNITS` in a remix. It installs scoped stock parameter formatter
pointers and widgets with a full-width held-lock highlight, plus an existing
`FormatterReg` adapter for stock `DELAY` TIME. Native numeric and dial shapes
are preserved.
It does not intercept arbitrary numeric drawing or replace other custom
modules' formatters. Conflicting stock parameter claims are rejected by the ledger;
a second DELAY TIME registration is rejected by the module's include check.

Custom modules can adopt the helpers from their own formatter wrappers using
the existing `Param.formatter_word` or `Linked.registers_formatter` mechanism.
Include `MUSICAL UNITS` in that remix and declare it in the client's `requires`.
No new registry or parameter metadata format is introduced.

| symbol | inputs | output |
|---|---|---|
| `mu_beats` | a0 buffer; d0 numerator 0..2048; d1 denominator 1..65535, in quarter notes | exact note name, otherwise ms/s at the engine tempo |
| `mu_milliseconds` | a0 buffer; d0 integer milliseconds 0..9999000 | compact ms/s |

Both helpers require six writable bytes, preserve d2–d7/a2–a6, and may clobber
d0/d1/a0/a1/CCR. The formatters use only stack/output writes. The dial wrapper also draws into
the existing LCD framebuffer. Unsupported inputs print
`?`; physical conversion requires tempo 30..300 BPM. Five characters occupy
at most 19 pixels in the stock small font. Musical matching uses rational
equality, never a tolerance; long exact cycles beyond the notation table use
seconds. Consumers supply the musical meaning and context of their values.

## Verification

`make check REMIX=musical-units` runs the linked-code gate, ABI/buffer/write
checks and native-font width checks. `tools/site/capture_manual.py
musical-units --project <local fixture>` captures the actual panel UART.
See [DEVELOPMENT.md](DEVELOPMENT.md) for timing provenance and limits.
No physical-device acceptance is claimed.
