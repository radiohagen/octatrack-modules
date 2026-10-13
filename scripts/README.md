# Repository tools

`check.py` implements source-only checks used by `make check` and GitHub Actions.
It checks tracked files, so add new files to the index before running it locally.
Submodules are pinned Git dependencies, not files to traverse for source hygiene.

`stage_octabam.py` plans a source copy into a clean, separate Octabam worktree at
the pinned commit. Add `--apply` to perform the copy. It rejects primary checkouts,
dirty trees, other revisions and paths that escape either workspace. It preserves
the imported native layout and never builds, flashes or changes the card.

The source repository and target must not be edited concurrently during staging.
After a stage, review the diff and run the required checks. Use a fresh target for
a later stage rather than overwriting changes in the previous one. There is no
force/clean/reset option. Follow [integration](../integration/README.md).
