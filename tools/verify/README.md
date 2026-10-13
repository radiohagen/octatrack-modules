# Imported module gates

These are the module-owned checks and shared MIDI test helpers from the source
commits in [sources.json](../../integration/sources.json). Their executable code
is preserved byte for byte during import.

Run them from a prepared Octabam integration worktree after staging, not directly
from this author repository. They depend on Octabam's toolpath, emulator, schema,
stock OS and sometimes copied project fixtures. Shared builder and emulator
implementations remain in Octabam. `make check` here checks source syntax and the
repository tooling; it does not execute these firmware gates.

Historical skips, failed mixed-engine cases and hardware limits remain in the
module documentation. Read the [current import evidence](../../docs/IMPORT_EVIDENCE.md).
