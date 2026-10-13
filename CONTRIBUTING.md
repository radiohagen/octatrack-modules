# Contributing

Read [branching](docs/BRANCHING.md), [verification](docs/VERIFICATION.md) and the
[integration workflow](integration/README.md).

1. Create a branch and worktree from current `origin/main`.
2. Keep changes limited to one feature or a necessary group of interacting modules.
3. Use a real neighbouring Octabam implementation as the starting point. The
   [template](modules/_template/README.md) lists the required decisions.
4. Run `make check`. For firmware, also record focused and combined Octabam results
   following its current contribution requirements. A green source CI is insufficient.
5. Open a pull request with behavior, provenance, exact checks and limitations.
6. Squash merge when reviewed, then delete the remote feature branch. Keep local
   worktrees until no task or build depends on them.

Do not add an empty passing test as evidence of firmware behavior. Keep original
evidence when importing a module; new packaging has not inherited a hardware test.
Use [migration](docs/MIGRATION.md) to bring over existing work without losing history.
