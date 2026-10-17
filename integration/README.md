# Build and source integration

`octabam.json` pins the Octabam integration used by the source staging tool.
Module source is stored at native Octabam paths. STORE, KITS, PLOCKS, the
builder and emulator are maintained in Octabam.

1. Clone `https://github.com/radiohagen/octabam.git` with its submodules.
2. Create a separate worktree at the commit in `integration/octabam.json`.
3. Run `python3 scripts/stage_octabam.py --octabam /absolute/worktree` here.
   It reports differences; `--apply` copies them after checking the target.
   Primary checkouts, dirty trees and a different baseline are refused.
4. Follow Octabam's BUILDING.md using your own OS 1.40C.

`sources.json` records imported source provenance and current file hashes.
The staging tool copies only its declared module, remix and verification files.
Recorded renames and `retired_files` remove obsolete tracked paths from the
isolated target; unrelated or untracked content is never retired.

[Developer notes and verification](DEVELOPMENT.md).
