# Branch and review workflow

`main` is the reviewed MIDI source. Use short-lived `codex/<feature>` branches
and separate worktrees after this initial bootstrap. Prefer one coherent change
per pull request and squash merges; remove remote branches after merging.

The local source gate is `make check`: structure, pin format, provenance hashes,
executable modes and staging safety. Firmware changes also require the relevant
Octabam checks. `integration/migration-validation.json` records actual checks;
no hosted Actions result is claimed. The imported Actions workflow is not copied
into this new repository: adding it requires suitable workflow authorization.
Source checks remain reproducible locally without firmware.

Before a source merge, inspect the PR, run checks on its final commit and record
the results. A solo owner can review their own work; zero required reviewers does
not waive review. Keep main protected from force pushes and deletion.

The Octabam fork's main stays at upstream. Integration and candidate PR branches
are separate, with their own validation. Never submit the whole integration
branch as a single upstream PR. See UPSTREAM_PLAN.md.
