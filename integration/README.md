# Reproduce the MIDI integration

The public [Octabam fork](https://github.com/radiohagen/octabam) contains the
`codex/integrate/midi` branch. `octabam.json` pins a concrete commit containing
shared fixes, module source and verification support. Unlike the earlier private
import baseline, this commit is published for a fresh public clone.

1. Clone `https://github.com/radiohagen/octabam.git` with its submodules.
2. Create a separate worktree at the commit in `integration/octabam.json`.
3. Run `python3 scripts/stage_octabam.py --octabam /absolute/worktree` here.
   The inspection reports differences; `--apply` copies only after all guards
   pass. It refuses primary checkouts, dirty trees and a different baseline.
4. Follow that worktree's BUILDING.md with your own OS 1.40C. Build using
   `make bus REMIX=harmony-track-bus BUILD=79 OCTABAM_PGO=0`.
5. Run applicable CONTRIBUTING.md checks and project-backed tests on disposable
   fixtures. See the remix README and the published validation record.

The author source and fork currently retain native Octabam paths. This is an
explicit staging workflow, not a completed external-adapter integration.
Per-module adapters and source-relative gate/generator paths belong in the
small upstream contributions, with byte and behavior checks at each step.
Shared STORE, KITS, PLOCKS, emulator and ledger changes remain in Octabam.

Source records preserve the original file SHA-256 and also the published hash
where documentation links were made portable. Never silently advance pins.

`make check` also verifies published source hashes and executable modes.
For a deliberate source edit, update `published_sha256` in the same reviewed
change and retain the original `commit`, `path` and `sha256` provenance.
