MUSICAL UNITS makes timing and pitch controls easier to read.
It changes the displayed value only. Every encoder setting remains available,
and saved values, parameter locks, scenes, MIDI and sound stay unchanged.

## Reading the display

| Display | Meaning |
|---|---|
| `1/16` | One sixteenth-note cycle or delay |
| `1/16T` | Sixteenth-note triplet |
| `1/16.` | Dotted sixteenth note |
| `123ms` | An intermediate duration, in milliseconds |
| `4.06s` | A duration in seconds |
| `STOP` | LFO speed is zero |

At 120 BPM, LFO SPD 64 with MULT 32 displays `1/16`. Turn SPD one step to
65 and it displays `123ms`. It still reaches that intermediate setting.
Increasing SPD makes the cycle shorter. MULT is included in the displayed
cycle, on audio and MIDI tracks, in both MAIN and SETUP.

The label describes a full nominal cycle. Retrigger, ONE, HALF and HOLD keep
their original behavior; the label is not a countdown or a measurement of
speed under modulation. Physical durations follow the current tempo and are
rounded to fit the native cells, so adjacent settings may share a label.

## Other converted controls

| Area | Display changes |
|---|---|
| MIDI NOTE LEN | Musical length or ms/s; native `0` and `INF` retained |
| ARP SPD and NLEN | Musical interval/note length or ms/s |
| ARP TRAN | Semitones, e.g. `12st` or `-7st` |
| Static/Flex RTIM | Retrigger interval as a division or ms/s |
| Recorder FIN/FOUT | Fade duration as a division or ms/s; `0ms` means no fade |

At 120 BPM, MIDI LEN 6 reads `1/16` and LEN 7 reads `146ms`. A sample
RTIM of `1.0` reads `1/16`; the next setting reads `132ms`. A recorder
fade of one sequencer step also reads `1/16`.

## Delay and other modules

Stock Echo Freeze TIME uses this notation with SYNC on. Its four-second
buffer limit displays `4s` when the requested delay would exceed it. With
SYNC off, TIME keeps its original numeric display.

Custom modules keep their own displays. Their authors can explicitly use
the shared duration helpers; arbitrary MIDI CC values are not assigned units
without knowing what the receiving instrument does. AMP envelopes, filter
frequencies, gain controls, sample STRT/LEN and recorder RLEN/QREC/QPL keep
their current displays until their context and physical mapping are supported.

## Evidence

The screenshots below come from the emulator's actual panel UART. Software
checks cover the formatters, timing scale, native font widths and original
parameter ranges. Physical-device acceptance remains outstanding.
