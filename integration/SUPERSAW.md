# CPU Supersaw development

This is a separate experiment authorized on 2026-10-21. It does not expand the
MIDI-only upstream contribution plan or change any existing package selection.
Source was recovered from `e789014` in this repository, originally imported from
Octabam `3bd99bca5d44ae6257112747070be77fef110839`. Its engine, tables and adapter
were verified against that source before modification.

Current integration starts at Octabam upstream
`8250be0c` with Synth's author submodule at
`525f4b19b04dc3ba3f3bae3b25abbf48df34a10a`.
Use an isolated worktree; do not use the MIDI staging helper or change its pin.
Copy `modules/supersaw/` and `tools/verify/verify_supersaw*.py` into that tree.
The small Synth wrapper change selects `modules/synth/engine.s`, whose body is
`.include "remix.inc"`, for its `poly` linked unit and supplies
`modules/supersaw/bridge.py:assembly` as the include callback. The pinned author's
submodule is untouched. Without SUPERSAW selected, it emits the author's original
source verbatim. The callback accepts the current `(modules, remix)` API.

Two integration selections are maintained in the companion Octabam worktree:
`supersaw` (all stock effects) and `supersaw-inserts` (current Octabam Inserts plus
SYNTH MACHINE and SUPERSAW). Both preserve the two per-track effect slots. No
Sophie, Post Fader or other experimental engine is added.

Commands, from Octabam:

```sh
make check REMIX=supersaw BUILD=S7
make rmx REMIX=supersaw-inserts BUILD=S7 RMX='SAW INSERTS S7'
OT_PROJECT=/path/to/local/project REMIX=supersaw-inserts BUILD=S7 \
  RMXNAME='SAW INSERTS S7' .venv/bin/python tools/verify/verify_supersaw_image.py
make check REMIX=supersaw-inserts BUILD=S7
```

Firmware/card images and private project fixtures stay in ignored local output.
Image-stage checks record the actual image SHA-256, commands and audio metrics.
Keep borrowed-idle failures and real-panel success as separate results. The
S4 eight-track gate injects actual keys and encoder input, verifies an audible
parameter change and note-off, and checks uninterrupted DSP output on both cores.
The earlier four/eight-track idle-call failures remain retained; they are not
a physical track-limit measurement. Hardware is not tested here.

S4 qualification is for the named image `SAW INSERTS S4`. Keep `BUILD` and
`RMXNAME` identical during rebuilds and compare the RMX hash with every receipt.
The standalone S4 full check passes; the broader combined suite still has the
retained S1 fixture exceptions described in the companion remix documentation.

S5 adds up to four notes per track using the pinned Synth allocator and AMP
records. Its standalone full check passes. All named-image cases pass, including
four-note MIDI with both FX occupied, sequencer chords and real-panel VOIC
transitions. Two final cases were completed separately after the first image
driver failed staging a fixture on a full disk; retain the original failure.
Additional rich tests pass on four tracks (16 notes); the 32-note stress case
misses later MIDI changes and is not qualified. Physical acceptance is still
unverified. The module source pin and final RMX hash identify this S5 evidence.

S6 follows the op1r two-saw-plus-sub topology, retaining the four-voice native
allocator and both FX slots. MORF replaces MIX. S4/S5 packages and receipts stay
unchanged; their seven-saw audio is historical, not S6 evidence.

S6 passes the standalone full check and all scoped exact-image cases: mono
regressions, native labels, eight-track DETU/MORF panel edits, four-note MIDI
with both FX occupied, sequencer chords, live mono/poly transitions and four
rich four-note tracks (16 notes). Both DSP capture paths remain continuous.
The sequence analyzer initially reported an octave error because it counted
zero crossings of the new paired waveform. A full-spectrum peak check confirms
C4; reanalysis passes on the unchanged capture. The original failure remains
retained. The first full check stopped on stale generated docs; the corrected
rerun passed. These are emulator results; hardware remains unverified.


S7 adds the optional CPU SEM filter per note. Main SRC is PTCH/DETU/MORF/CUT/SUB/DRIV;
SETUP is FINE/RES/ENV/DEC/TYPE/blank. CHRD generation/recording is removed only
on Supersaw. The native author submodule is unchanged. New gates compare actual
Spectrum response, linked arithmetic, real SETUP encoders and native project
save/cold reload. Retain failed reference probes separately from corrected results.
The new tagged setup row is not an older-firmware project compatibility promise;
use disposable project copies for validation.
