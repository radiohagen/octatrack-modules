# Give TEMPO SYNC hook symbols unambiguous names

The generic cave/replay symbols can resolve to another linked unit when TEMPO SYNC is combined with MIDI modules. Give the publish/replay entry points unique names and execute the installed hook in a regression covering all eight tracks, release notes, surrounding bytes and registers. No new effect behavior is introduced.

Base: upstream `2d1cbcf471cf8b63e2279b3c372a6ebb47456a99`. Candidate branch: `codex/pr/tempo-hook-symbols`.
This prerequisite is independent of the new MIDI feature modules.

## Validation

Branch-specific builds, documentation checks and focused regressions passed. Results are recorded in
`integration/review-branches.json`. Full current `make reach RUN=1 KEEP=1`
qualification is still required after rebasing immediately before submission.
Historical full-integration results are documented separately and do not
substitute for that qualification. Physical hardware has not been tested.

This is a prepared description; no upstream PR has been opened.
