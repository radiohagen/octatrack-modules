# Branches and releases

## One main branch

`main` holds reviewed, reproducible source. It can contain experimental modules
whose limitations are explicit. Being on main does not mean hardware acceptance.
There is no permanent `develop` branch and no permanent branch per module.
Folders separate modules; branches separate changes.

After the initial bootstrap, use pull requests for changes to main. Use squash
merges so each change is understandable and revertible. A solo maintainer may
review and merge their own PR; do not require an unavailable second approver.
Source CI must pass when the runner can execute. If GitHub cannot start any steps
because of an account/billing restriction, record that external blocker in the
PR and run the identical `make check` locally on the final tree. Do not describe
that as passing hosted CI. This exception does not apply to failing check steps
or replace any required firmware checks. Read the evidence before merging.

## GitHub settings at bootstrap

Verified on 2026-10-13: this repository is private, `main` is the default,
squash merging is enabled, merge/rebase merging is disabled, and merged remote
branches are deleted automatically.

GitHub refused branch protection because the account needs Pro for a private
repository. PR/check requirements are therefore a documented convention, not
server-enforced. When available, protect main with required PRs, the
`source-checks` status, current-base checks, resolved conversations, linear
history and no force pushes or deletion. Zero required approvals supports solo
maintenance; review still happens on the PR.

The first Actions job was also blocked before any steps started: GitHub reported
failed recent payments or a spending limit requiring attention. The workflow is
configured; it has not passed on a hosted runner. Local `make check` passed.
After account access is restored, rerun the workflow and update this status.

## Feature branches and worktrees

Examples: `codex/midi-arp-presets-extraction`, `codex/midi-follow-octave`,
`codex/integration-octabam-update`. Use a short-lived `codex/experiment-...` branch
for a probe. Keep a useful experiment with a clear status; do not merge broken
or undocumented work just to tidy branches.

From the main checkout:

```sh
git fetch origin
git worktree add .worktrees/midi-arp-presets-extraction \
  -b codex/midi-arp-presets-extraction origin/main
```

Push the branch and open a PR. Update from main before final verification. Do not
force-push shared branches; use `--force-with-lease` only on your own feature
branch when its history must be rewritten. Delete remote branches after merge.
Archive local worktrees only after checking active work and ignored artifacts.

## Integration across two repositories

This repo is authoritative for a module after verified migration. Octabam imports
an exact commit with its existing submodule/adapter pattern. Changes to shared
Octabam infrastructure go in a separate Octabam PR.

During development an Octabam feature branch can pin the module feature commit.
After squash merge, bump that pin to the resulting main commit and rerun the
relevant checks. Evidence must name the final commit, not only the old PR head.
Production selections must not silently track an author's moving branch.

## Tags

Use annotated repository-wide tags `v0.1.0`, `v0.1.1`, etc. once there is an
intentional source release. A single version covers a coherent snapshot of all
modules; module-level versions can wait until independently released modules
actually require them. Before 1.0, use a minor version for incompatible changes
and a patch version for compatible fixes. Document compatibility explicitly.

A release names the Octabam commit, module commit, selected remix, local image
hash and verification limits. Keep proprietary or generated firmware files out
of release assets. Never retarget a published tag. No initial version tag is
created for the initial foundation or source import.
