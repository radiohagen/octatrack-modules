# octatrack-modules

Mattias Wolff's home for independently maintained Octatrack firmware modules.
Modules are composed into firmware by [Octabam](https://github.com/sambanks/octabam),
using the owner's copy of the official OS 1.40C.

**Status: 12 modules imported — eight features and four supporting modules.**
The source, generators, focused gates and native remix selections are preserved
from exact commits in [the Octabam fork](https://github.com/mattiaswolff/octabam).
See the [module catalogue](modules/README.md) and
[import evidence](docs/IMPORT_EVIDENCE.md).

This is a source import. Manifests and gates currently retain their Octabam-tree
paths and execute in a prepared Octabam integration worktree. No active firmware
checkout, package, card or device has been switched to this repository. External
submodule adapters are a subsequent migration step, not implied by the import.

## Start here

Python 3.12 or newer, Git and Make are enough for the repository checks:

```sh
git clone --recurse-submodules git@github.com:mattiaswolff/octatrack-modules.git
cd octatrack-modules
make check
```

Firmware work also needs an isolated Octabam checkout and its documented
toolchains. Follow [integration](integration/README.md) when migrating a module.

## Layout

| Location | Purpose |
| --- | --- |
| [modules/](modules/README.md) | One directory per module: source, Octabam manifest, focused gates and documentation |
| [modules/_template/](modules/_template/README.md) | An intentionally inactive starting point |
| [integration/](integration/README.md) | Exact Octabam reference revision and import workflow |
| [remixes/](remixes/README.md) | Our selections and combined acceptance cases; Octabam executes them |
| [tests/](tests/README.md) | Tests that run without proprietary firmware |
| [scripts/](scripts/README.md) | Source checks and guarded staging into an isolated Octabam worktree |
| [tools/verify/](tools/verify/README.md) | Imported module gates, executed inside Octabam |
| [docs/](docs/README.md) | Branching, verification and migration decisions |
| `artifacts/` | Ignored local reports and build output |

## Working agreement

- `main` is the reviewed source of truth. Hardware status is recorded separately.
- Work on short-lived `codex/<module>-<change>` branches in separate worktrees.
- Merge through pull requests after checks; squash merge and delete the branch.
- Use repository-wide `v0.x.y` tags for deliberate source releases. No release yet.
- Pin both repositories to commits for integration. Never silently follow a branch.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [branch strategy](docs/BRANCHING.md).
Hosted CI and private branch protection currently have account restrictions;
the branch guide records the actual settings and local-check fallback.
No Elektron firmware, samples, card contents or generated firmware images belong
in this repository or its GitHub releases. See [THIRD_PARTY.md](THIRD_PARTY.md).
