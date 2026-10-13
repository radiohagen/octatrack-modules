# Octabam integration

[octabam.json](octabam.json) pins the existing fork baseline needed by the imported
modules. [sources.json](sources.json) records each module's origin and every
imported file's original SHA-256. File keys identify current paths; each record's
`path` and hash preserve its original source location and bytes. [Import evidence](../docs/IMPORT_EVIDENCE.md)
distinguishes source identity, a combined build and physical behavior.

## Current source-import workflow

The imported source deliberately retains its native Octabam paths. Run
`scripts/stage_octabam.py --octabam /path/to/isolated-worktree` to inspect the
staging plan, then add `--apply` to copy it. The target must be a clean, separate
Git worktree at the pinned commit; the main checkout and other revisions are
refused. Recorded renames also retire the tracked original files in that clean worktree,
so both module names cannot be discovered at once. The script stages source only
and never builds or accesses a device.
Initialize required submodules and follow that worktree's setup instructions.
Run gates from the resulting Octabam tree; running imported gates directly from
this repo does not supply the builder, firmware or shared harness.

The following author-adapter pattern is the **next migration stage**. It has not
replaced this source-import workflow or any existing release path.

## Prepare the builder

Use the existing local Octabam repository, which contains the pinned commit,
to create a separate worktree at that commit. This baseline is **local-only**:
GitHub could not resolve it during import. A fresh remote clone alone cannot
reproduce it yet, and this task does not publish the private integration history.

From the existing local Octabam repository:

```sh
git worktree add .claude/worktrees/module-integration \
  -b codex/module-integration 3bd99bca5d44ae6257112747070be77fef110839
```

Read its AGENTS.md, initialize required submodules, and use the existing setup
instructions for the toolchains and owner-supplied stock OS. Keep fixtures local.
Do not repoint an active integration checkout. Publishing a reproducible supported
builder baseline is required before presenting this as a fresh-clone build workflow.

## Import a migrated module

Follow Octabam's existing pattern: an author repo pinned under
`modules/<slug>/upstream` and a small `modules/<slug>/manifest.py` that executes
the author's declaration. The source declaration here lives at
`upstream/modules/<slug>/manifest.py`.

Once that module exists, the adapter takes this form (replace `<slug>`):

```python
from pathlib import Path
import runpy

source = Path(__file__).resolve().parent / "upstream" / "modules" / "<slug>" / "manifest.py"
MODULE = runpy.run_path(str(source), run_name="author_module")["MODULE"]
```

The author's manifest resolves source paths from its own `__file__`, so moving
the checkout cannot silently select another copy of the source. Gate paths must
satisfy Octabam's schema: currently repo-relative under `modules/` or `tools/`.
Check gate execution and imports as part of extraction; a source path fix alone
does not relocate the test harness. Preserve the module's current key and claims. MIDI Arp Presets now uses
`MIDI ARP PRESETS`; older external selections must be updated explicitly.

This repository is private. Anyone consuming its submodule needs access; a public
upstream PR must not acquire an inaccessible private dependency. Initially keep
the integration in the owner's fork. Choose publication or an agreed source
contribution before proposing adoption by public upstream.

## Check and promote

Run the module-only selection and the actual combined remix with Octabam's
`make check REMIX=<name>` and applicable contribution gates. Record both repo
commits and the built image hash. Keep fixtures and outputs out of Git.
The normal hosted CI here does not have firmware or build the firmware.

Advance the integration pin deliberately after a module PR merges. A pin update
is reviewable on its own and includes verification on the new pair of commits.
