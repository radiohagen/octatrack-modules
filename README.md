# Octatrack MIDI modules

Author source for MIDI Scales, MIDI Loopback, MIDI Follow and MIDI Harmony,
maintained under [radiohagen](https://github.com/radiohagen). Octabam provides
the builder, schema, shared platform and emulator.

This repository contains the selected MIDI source from the completed
track-local Harmony integration, plus focused gates and test selections.
It excludes ARP templates, new synth engines and unrelated effects. Existing
stock modules in the Octabam fork are unchanged unless explicitly documented
as a required integration fix.

- [Module catalogue](modules/README.md)
- [Build and integration](integration/README.md)
- [Small upstream PR plan](docs/UPSTREAM_PLAN.md)
- [Verification boundaries](docs/VERIFICATION.md)
- [Source provenance](integration/sources.json)
- [Licensing and attribution](THIRD_PARTY.md)

Run `make check` for source checks and staging safeguards. Building firmware
requires the owner's OS 1.40C and the pinned public Octabam integration below.
No firmware, samples or device projects are distributed here.

`main` is the reviewed migration source. Make future changes on short-lived
`codex/<feature>` branches in worktrees. The migration preserves native build
paths; per-module external adapters will be qualified in the upstream series.
