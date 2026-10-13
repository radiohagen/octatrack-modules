# Migration from the Octabam fork

This foundation does not move existing modules or change their active sources.
The full fork remains the integration workspace. Extract one module at a time.

## First candidate: ARP PRESETS

Inspected on 2026-10-13 at source commit
`e753f1dc4206accd97ccc908d9a72d0d9c039cc8` in
[mattiaswolff/octabam](https://github.com/mattiaswolff/octabam).
It has its own module folder and two focused gates, making it a useful first
candidate. This is a provenance starting point, not a claim that it is still the
latest branch head. Recheck branches, working changes and integrated builds.

Known extraction work: its Linked source currently uses an Octabam-root-relative
path and its gates live under `tools/verify/`. Keep its generator inputs, generated
assembly, checks and documentation together; resolve paths through the manifest
and retain any required thin gate adapters in Octabam.

## Migration acceptance

1. Identify the exact authoritative source commit, active changes, authorship,
   licence and existing evidence. Do not overwrite work from another session.
2. Establish a passing baseline in an isolated Octabam worktree with its original
   module and the intended combined selection.
3. Import only the module-owned files. Record source repo, commit, original paths
   and any path-only edits in the import commit and module README. Preserve all
   relevant copyright notices. Keep the original repository history available.
4. Use the existing Octabam adapter/submodule convention to point at the extracted
   module. No firmware behavior change belongs in the extraction PR.
5. Run focused and combined checks on the final commits. Compare the old and new
   generated images for byte identity. Record any report-only path differences.
6. Only then switch the integration pin and declare the new module authoritative.
   Retain earlier branches and packages until their active dependencies are known.

Inventory MIDI Follow, Harmony, loopback, routing and other work separately before
extracting it: their shared hooks and bridge modules may need a coordinated import.
Do not assume a folder copied out of the fork is already independently buildable.
