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
make check REMIX=supersaw BUILD=S8
make rmx REMIX=supersaw-inserts BUILD=S8 RMX='SAW INSERTS S8'
OT_PROJECT=/path/to/local/project REMIX=supersaw-inserts BUILD=S8 \
  RMXNAME='SAW INSERTS S8' .venv/bin/python tools/verify/verify_supersaw_image.py
make check REMIX=supersaw-inserts BUILD=S8
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


S7 passes the standalone full check and the exact `SAW INSERTS S7` image cases:
mono/sequencer regressions, mixed Supersaw/FM with both FX occupied, eight-track
DETU/MORF panel edits, four-note MIDI with OFF and LP, filtered mono/poly
transitions, SETUP/CUT encoders, native save/cold reload and page resolution.
Four filtered notes on one track are qualified; no larger filtered-polyphony
claim is made. Four smooth OFF/LP/BP/HP example renders have audible AMP release
and silent endings. The first audio launch stopped before rendering because the
Spectrum reference build replaced shared runtime symbols; the runner now restores
the candidate afterward. Initial failure logs remain beside corrected passes.
These are source/emulator results; physical hardware remains unverified.


## S8 control, level and CPU update

TYPE is the native four-position OFF / LOW / BP / HP switch; pressed encoder
input also advances one position. A single note keeps its mono level at VOIC
1..4 instead of the inherited -3.01/-4.77/-6.02 dB reduction. Notes retain
independent AMP release and filter state, and both FX slots remain available.
The chord sum saturates at full scale; dense/driven chords can reach that limit.

The CPU audit preserves oscillator interpolation, sample rates and exact filter
sample/state arithmetic. Four-note steady render counts fall by 6.6-11.7% with
filter OFF and 23.3-27.6% with LOW/BP/HP across the plain/rich fixtures. A 280-probe
profile covers mono and one to four poly voices, all types, cold/warm calls,
cutoff and pitch changes, attack, release and silent tails. 279 probes improve;
the rich mono OFF attack increases from 1,119 to 1,123 instructions (+0.36%).
These are executed ColdFire instructions, not measured hardware cycles or CPU
headroom. The filter oracle checks 100,000 modulation blocks bit-for-bit.


S8 passes the standalone `make check REMIX=supersaw BUILD=S8` (project cases
separate), module source checks (24 tests), and all 11 project-backed cases on
the exact named `SAW INSERTS S8` image: mono/sequencer, mixed FM and occupied FX,
eight-track DETU/MORF panel edits, four-note MIDI, live mono/poly transition,
filter controls, native save/cold reload, VOIC level/TYPE switch and filtered
four-note MIDI. The native descriptor and linked arithmetic gates also pass.
One-note levels at VOIC 1..4 differ by less than 0.003 dB. The rendered native
TYPE widget was visually inspected. Three LOW/BP/HP example captures have
verified releases, silent endings and unused FX slots.

Image SHA-256: `00d68934661a16d503e633b0021499259035eb155ed342db1b05c29eaf9176ad`.
These are source/emulator checks; physical playback and CPU headroom remain
unverified. This does not replace the broader Inserts suite's retained fixture
exceptions or extend the one-track filtered-polyphony qualification.


## S9 adaptive CPU candidate

The current source moves the per-voice filter before the 2x interpolator,
with a 9 kHz ceiling. Neutral fully open LOW automatically bypasses; zero-gain
blocks skip synthesis; optional sub/drive work is selected once per block.
Drive uses a bounded five-PCM-unit approximation, and the filter envelope
advances at block rate. Four voices, separate releases, all filter modes and
both FX slots remain. See the module README for audible compatibility changes.
The previous S8 sample-exact/filter-response claims do not apply to S9.

## S10 lifecycle follow-up

S10 is based on author commit `007a049` (S9), the source used by the RADBUSS2
hardware diagnosis. Copy the complete module directory, including
`diagnostics.h`, and all `verify_supersaw*.py` scripts. The native Synth pin and
Part layout do not change. Production generation/builds leave `SS_DIAGNOSTICS`
unset; optional instrumented builds must set it to `1` for both generation and
composition. Keep their image hashes and timing evidence separate.

The new lifecycle verifier needs the existing corrected ColdFire EMAC library;
set `LIBUNICORN_PATH` when using an isolated build. Do not substitute the default
Python Unicorn wheel for native pitch arithmetic. `verify_supersaw_poly.py
--burst` adds batched MIDI input, and recognizes diagnostic symbols to retain
frame-stamped enqueue/allocation events and per-voice state in its receipt.
Source/emulator results do not resolve the hardware burst-start overrun. See
the module README for the bounded hardware replay and diagnostic layouts.
