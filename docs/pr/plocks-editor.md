# Preserve page-two locks when releasing an edited trig

Releasing a trig after editing a page-two lock can take the native tap-to-clear path and remove the lock just entered. Restore the native edited flag and clear pending tap masks after an edit; retain ordinary tap-to-clear behavior and unchanged PLOCKS storage/capacity. The fixture normalization and explicit release checks make this regression reproducible.

Base: upstream `2d1cbcf471cf8b63e2279b3c372a6ebb47456a99`. Candidate branch: `codex/pr/plocks-editor`.
This prerequisite is independent of the new MIDI feature modules.

## Validation

Branch-specific builds, documentation checks and focused regressions passed. Results are recorded in
`integration/review-branches.json`. Full current `make reach RUN=1 KEEP=1`
qualification is still required after rebasing immediately before submission.
Historical full-integration results are documented separately and do not
substitute for that qualification. Physical hardware has not been tested.

This is a prepared description; no upstream PR has been opened.
