# MIDI Follow integration

MIDI Follow requires **STORE** native Part access and upstream **EVENTS**.
STORE native Part access is upstream in
[#976](https://github.com/sambanks/octabam/pull/976); it replaces the retired
MIDI PART STATE helper without changing native saved settings. EVENTS owns
transport start/resume and accepted-note notifications; Follow owns source
notes, register history and the musical response. EUCLID can subscribe to the
same transport notifications.

The current integration is [Octabam PR #824](https://github.com/sambanks/octabam/pull/824).
EVENTS was merged upstream in [#871](https://github.com/sambanks/octabam/pull/871).
The PR selects this repository through `modules/midi-follow/upstream` and
records the exact source commit. No standard remix gains Follow.

## Build

1. Clone `https://github.com/radiohagen/octabam.git` and fetch
   `codex/pr/midi-follow-voices`.
2. Create an isolated worktree at that branch and initialize its submodules.
   Keep the committed submodule pins to reproduce the reviewed source.
3. Follow Octabam's build instructions using your own OS 1.40C.
4. Run `make check REMIX=midi-follow` for the standalone selection and
   `make check REMIX=midi-follow-events` for the selection with EUCLID,
   PLOCKS P2, MIDI Scales and MIDI Loopback.

Project-backed captures check physical-control input in the emulator and the
resulting MIDI bytes. Source checks in this repository do not build firmware.
The PR records exact builds, checks and remaining hardware tests.

Targeted MKII testing on 30 October 2026 used MFOL30U / BUILD FB, based on
Octabam `520be921` and author source `22bbdab`. USB MIDI captures passed the
four-note baseline, ten-minute seven-follower GRAV LIVE runs at 200 BPM in
fan-out and chain configurations, and a five-minute run alongside eight audio
tracks. Pitches, counts, cadence and note releases passed. The operator also
confirmed smooth audio and responsive controls during the combined run.

The eight-track native control at 300 BPM and 2× pattern speed froze the unit
with RFOL OFF; Follow remained loaded in the remix, so this does not isolate
the responsible component. The requested traffic exceeds physical DIN capacity.
Native MIDI transmit-queue handling is a suspected cause based on source
inspection and timing; the hardware failure location has not been measured.
MKI, DIN timing and safety across every configuration remain unverified.

Use a disposable project copy for physical testing; saving a bank in stock
firmware resets Follow's register and update settings as described in the
[module README](../modules/midi-follow/README.md).

## Project-backed MIDI checks

In the matching Octabam worktree, build `make bus REMIX=midi-follow-events`,
then run these commands with a disposable project template:

```sh
python3 tools/verify/verify_midi_follow.py midi-follow-events --project /path/to/project
python3 tools/verify/verify_midi_follow_register_port.py --project /path/to/project
python3 tools/verify/verify_midi_follow_response_port.py --project /path/to/project
python3 tools/verify/verify_midi_follow_gravity_port.py --project /path/to/project
python3 tools/verify/verify_midi_follow_voices_port.py --project /path/to/project
```

The register capture covers all three modes, independent remembered values,
track changes and closing/reopening FOLLOW. The response capture includes
native source chord voices in TRIG and LIVE; the four-voice capture verifies
empty follower slots and balanced releases. Each script prepares a separate
virtual project copy and leaves the supplied template unchanged.
