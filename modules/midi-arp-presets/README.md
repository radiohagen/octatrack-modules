# MIDI Arp Presets

Build selector: `MIDI ARP PRESETS`. Module and standalone remix: `midi-arp-presets`.
The name is consistent across source, build selection and verification tools.

A separate MIDI module for OS 1.40C. On **MIDI ARP SETUP** (FUNC + AMP),
turn **A** to load a rhythm. The title shows `ARP A:TRESILLO`, for example.
**C remains LEN; F remains KEY.** TRIG step toggles, held-TRIG + LEVEL pitch
editing and FUNC + LEFT/RIGHT rotation remain native.

Loading replaces the current track's arp length, active-step mask and all
16 pitch offsets. It leaves MODE, SPD, RNGE, NLEN, LEG, TRAN, KEY and the
input chord alone. Enable the arp on its main page to hear it. Names such as
EIGHTHS assume SPD 6 (sixteenth-note ticks); every preset follows your SPD.

Turn either way from CUSTOM to start at STRAIGHT; then browse with A.
The ends clamp. A report containing several ticks advances one preset.
After a manual edit, the title reads CUSTOM unless the result exactly
matches another preset. Recognition uses the actual native bytes, so
changing track/Part, copy/paste or reload cannot leave a stale preset name.
There is no additional preset-number storage. Use native arp copy/paste to
keep an existing custom pattern before browsing; there is no preview/undo
bank in this first version.

Selection takes effect immediately without restarting the arp or sending a
new chord. It retains the native arp phase; it is not bar-quantized.
The existing Part/project save and reload paths own the loaded pattern.

## Musical speed labels

ARP MAIN's SPD readout shows `1/16` instead of `x6`, `1/8` instead of
`x12`, and the other exact straight divisions. `T` means triplet (`16T`
is a sixteenth-note triplet); `D` means dotted (`16D` is a dotted
sixteenth). Unusual values keep the native `xN` label. All 96 settings,
encoder increments, locks, Scenes and LFO values remain native.

The [Elektron manual](https://www.elektron.se/wp-content/uploads/2024/09/Octatrack-MKII-User-Manual_ENG_OS1.40A_210414.pdf),
section 15.4.3, defines 6 as sixteenths and 12 as eighths. These numbers
count clock ticks: 24 per quarter note, 96 per whole note. A larger value
means a longer gap. Labels describe each arp tick; skipped steps lengthen
the gaps between sounding notes. Track scale does not redefine the label.

## Rhythm bank and sources

`x` = active step, `.` = rest. These are equal-pulse onset patterns, not
velocity accents, swing, or full reproductions of a musical style.

| Name | Ticks | Pattern | Pitch offsets |
|---|---:|---|---|
| STRAIGHT | 16 | `xxxxxxxxxxxxxxxx` | none |
| EIGHTHS | 16 | `x.x.x.x.x.x.x.x.` | none |
| OFFBEAT | 16 | `..x...x...x...x.` | none |
| PULSE4 | 16 | `x...x...x...x...` | none |
| TRESILLO | 8 | `x..x..x.` | none |
| CINQUIL | 8 | `x.xx.xx.` | none |
| SON3-2 | 16 | `x..x..x...x.x...` | none |
| SON2-3 | 16 | `..x.x...x..x..x.` | none |
| E5/16 | 16 | `x..x..x..x..x...` | none |
| E7/16 | 16 | `x..x.x.x..x.x.x.` | none |
| E3/7 | 7 | `x.x.x..` | none |
| E2/5 | 5 | `x.x..` | none |
| E4/9 | 9 | `x.x.x.x..` | none |
| E5/12 | 12 | `x.x.x..x.x..` | none |
| OCTPULSE | 8 | `x.x.x.x.` | steps 5 and 7: +12 |
| OCT332 | 8 | `x..x..x.` | step 7: +12 |
| KENTBASS | 16 | `.x.x..x...x..x.x` | none |

The traditional timelines and Euclidean family follow Godfried Toussaint,
[The Euclidean Algorithm Generates Traditional Musical Rhythms](https://cgm.cs.mcgill.ca/~godfried/publications/banff.pdf)
(2005), section 4: tresillo E(3,8), cinquillo E(5,8), son clave and
evenly distributed pulses. SON2-3 rotates SON3-2 by eight ticks; the E(k,n)
labels explicitly identify onset count and cycle length rather than claiming
a particular performance tradition. The selected rotations start on a hit.
At SPD 12, the 16-tick son timeline spans two 4/4 bars; at SPD 6 it is
compressed into one. Seven-, five- and nine-tick cycles move against 4/4.

Jajoria, Krenn and Mäder,
[Towards a computational definition of the tresillo rhythm and its tracing in popular music](https://arxiv.org/abs/2109.10256)
(2021), provides a second musical source for treating tresillo as a reusable
rhythmic figure across songs. The straight/offbeat controls and two octave
variants here are original practical arrangements, not transcriptions from
those papers. Octave offsets interact with the existing RNGE and note bounds.

KENTBASS is the requested offbeat-only approximation of the opening bass
rhythm in Kent's [Vals för Satan (din vän pessimisten)](https://www.youtube.com/watch?v=-XDsjqiYjKU).
It activates steps **2, 4, 7, 11, 14 and 16**, with no pitch offsets.
The four-on-the-floor kick positions **1, 5, 9 and 13 are rests**. The mixed
recording does not establish whether bass also retriggers under the kick;
this deliberately excludes those uncertain attacks, rather than claiming an
isolated-stem transcription. Try SPD `1/16` (`x6`), LEN 16 and a repeated
root near 126 BPM. Loading the preset does not change tempo or SPD.
A comparison of the first 20 bars (approximately 0:00.18–0:38.28), using
300–850 Hz attack-strength measurements and excluding the kick positions,
found the same six strongest offbeat attacks in every bar. This supports a
16-tick onset cycle without drift against the kick in that opening; it does
not determine any longer filter, accent or other-layer cycle.

## Implementation boundaries

Two independent editor hooks: the ARP SETUP encoder branch at `0x4007a2fc`, and
the title call at `0x40079d68`. No playback, MIDI send, KITS, MIDI SCENES,
KEY, or persistence-format changes. The KEY branch at `0x4007a3e2` stays
available to MIDI SCALES. The combined `mattias-bottleservice` panel gate
selects C Dorian with F and then CINQUIL with A, preserving the extended
KEY byte and its native readout. Revalidate other module combinations.
SPD replaces only the formatter pointer at
`0x400d40a6`; uncommon/invalid values call the native `0x4003b840` formatter.

The native writers establish these offsets (Part stride `0x18b2`):

| Data | Bank RAM offset | CS1 address | Track stride |
|---|---|---|---:|
| LEN minus one | `0x8f270` | `0x100a53be` | 36 |
| active steps, u16 | `0x905a2` | `0x100a66f0` | 2 |
| signed offsets, 16 bytes | `0x905b2` | `0x100a6700` | 16 |

LEN also updates `0x46c76dee + track*68`, as the stock editor does. Mask
and offsets have no equivalent live mirror in those native edit paths.
Dirty flags match stock. A bounded interrupt-masked block publishes the
pattern and restores SR; it never resets note ownership or arp phase.
No mutable module state, SRAM reservation, new file or dependency is added.

`presets.c` and `hooks.s` are authoritative. `generate.py` compiles them to
the checked-in `presets.s` consumed by Linked, following BRAIN's approach.

## Verification

`tools/verify/verify_midi_arp_presets.py` executes the built code in ColdFire
Unicorn: 1,088 applications covering 17 rhythms × 4 Parts × 8 tracks ×
first/last bank; exact Part/CS1/live writes and dirty flags; custom matching,
invalid contexts, encoder bounds, title text, ABI and interrupt-mask
restoration. Native C/F/LEVEL and both rotation paths compare equal to stock.
All 96 SPD values and invalid inputs pass a rational musical-duration
oracle, buffer bounds and ABI checks through the installed formatter.
Display/LED calls are stubbed in that focused gate.

`tools/verify/verify_midi_arp_presets_port.py` stages a silent copy of
`OT_PROJECT` (or `--project`) and runs the native FUNC+AMP/A panel events,
captures the LCD, browses to KENTBASS, saves through the PROJECT menu, and
cold-loads the saved virtual card with its six offbeat attacks intact. With MIDI SCALES selected it also checks the F/A interaction
and captures the extended scale beside the preset title. A 3.48-second MIDI capture produces 28 STRAIGHT, 11
TRESILLO and 10 KENTBASS onsets from the same root; a switch to OCT332 while the root is
held reaches +12 without another sequencer trig. Note releases are checked.
`--midi-only` repeats just the playback cases during development.

Run `make check REMIX=midi-arp-presets OT_PROJECT=/path/to/project` for both gates
and the repository checks. Only owned copies and virtual cards are modified.
Historical pre-rename result: passed on 2026-10-13 with a copy of OT-MIX-FLEX, including audio and reserve
write checks. The shared fixture's unrelated T2 FX2 CC40 probe was skipped
because that probe requires a different effect; both MIDI Arp Presets gates ran.

Current rename checks are recorded in [the rename evidence](../../docs/MIDI_ARP_RENAME.md).

Hardware acceptance remains open: encoder feel, live switching with external
synths, physical MIDI timing and held-note behavior on the selected remix.
