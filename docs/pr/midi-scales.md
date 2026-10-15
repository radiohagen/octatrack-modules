# Add MIDI Scales to the native ARP KEY control

The native KEY selector offers Major/Minor only. Add Dorian, Phrygian, Lydian,
Mixolydian and Locrian for all twelve keys, preserving OFF, existing IDs and
native Part storage. Extra modes snap to nearest scale notes, with ties down.
This standalone feature does not require Follow, Loopback or Harmony.

Base: upstream `2d1cbcf471cf8b63e2279b3c372a6ebb47456a99`. Branch: `codex/pr/midi-scales`.
Author source: [the complete narrow source diff](https://github.com/radiohagen/octatrack-modules/commit/9d31ce2ff977205bdd3c17a58e55f86bc11376ac).
The source branch contains only this module and its documentation/licence;
Octabam supplies the adapter, harness, gate, manual and standalone test remix.
Assembly matches the completed implementation. The author manifest resolves
assembly relative to its own location.

## Validation

The full standalone make check passed (two project-dependent checks skipped).
Adapter and native builds are byte-identical at SHA-256
`d3a2476762978a946d1733c2f153ea23ab67b81ee40017d0349e2cbc65a3edcf`.
Exact branch results are in `integration/review-branches.json`. Checks cover
84 key/mode combinations over all 128 notes, legacy IDs, OFF/invalid choices,
formatter guards and native encoder bounds. Full `make reach RUN=1 KEEP=1`
qualification is still required on current upstream immediately before
submission. Hardware is untested. No upstream PR has been opened.
