# Contributing

Read [the upstream sequence](docs/UPSTREAM_PLAN.md) and
[integration instructions](integration/README.md). Work in a short-lived
`codex/<feature>` worktree and keep source changes reviewable. Preserve existing
credits and record provenance. Run `make check`; firmware changes additionally
need the applicable current Octabam checks on the exact staged source.

Use a PR for author-source updates. Prefer squash merge for a coherent change;
do not squash away required provenance. A source PR is not upstream acceptance
and does not establish device behavior. Keep integration pins deliberate.
