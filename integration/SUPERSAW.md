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
make check REMIX=supersaw BUILD=S4
make rmx REMIX=supersaw-inserts BUILD=S4 RMX='SAW INSERTS S4'
OT_PROJECT=/path/to/local/project REMIX=supersaw-inserts BUILD=S4 \
  RMXNAME='SAW INSERTS S4' .venv/bin/python tools/verify/verify_supersaw_image.py
make check REMIX=supersaw-inserts BUILD=S4
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
