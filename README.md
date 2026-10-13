# octatrack-modules

Mattias Wolff's home for independently maintained Octatrack firmware modules.
Modules are composed into firmware by [Octabam](https://github.com/sambanks/octabam),
using the owner's copy of the official OS 1.40C.

**Status: repository foundation. No firmware modules have been migrated yet.**
Existing source branches, packages and evidence remain in
[mattiaswolff/octabam](https://github.com/mattiaswolff/octabam).
This repository does not currently build a firmware image.

## Start here

Python 3.12 or newer, Git and Make are enough for the repository checks:

```sh
git clone git@github.com:mattiaswolff/octatrack-modules.git
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
| [scripts/](scripts/README.md) | Small repository checks, not a second firmware builder |
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
