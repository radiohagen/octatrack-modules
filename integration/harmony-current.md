# Harmony on current EVENTS and STORE

Review branch: `codex/harmony-follow-review-20261026` in the author and
Octabam repositories. The integration starts at Octabam
`f79ad3cab83a1cd7aae4c87b8500f9d63256d854`; author changes start at
`fde8036c42117ed61a29b7c72206d40135c2f11e`. This is separate from Follow PR #824.

Select STORE, EVENTS, MIDI SRAM and MIDI HARMONY. MIDI FOLLOW and MIDI SCALES
remain optional. Harmony and SRAM resolve source relative to their author
manifests; the integration pins the source through its adapters. Use the
integration's verifiers and shared harness alongside the matching source.

Required platform changes are registered Harmony transport/accepted-note/edit
callbacks, the optional EVENTS post-copy notification, and STORE checked
bank-write/copy callbacks plus post-new-project notification. Native copies
execute once. A native file-copy failure must prevent companion writes; a
negative checked-client result propagates to the native caller. No persistence
format, retained allocation or native Part field assignment changes here.

The LIVE regression predates the stock-scale Follow patch: in C major,
a held C–E–G became D–F-sharp–A while a fresh Harmony trig produced D–F–A.
The fix moves Harmony-owned pitches by scale degree, preserving inversion
and octave spread. Explicit MAJ/MIN/DOM7 and KEY OFF move chromatically.
Native Follow retains its existing scale/offset implementation.

Focused checks cover event registration and native register/CCR preservation,
STORE refusal/copy errors, load and clipboard lifecycle, Harmony arithmetic,
Follow ownership/deadlines and project-backed sequencer/UART playback.
The integration's review receipt records exact commands, results, image hashes,
skips and remaining qualification boundaries. Source `make check` is a separate
check and does not establish firmware behavior. Physical hardware testing is
outstanding; this review neither modifies a device nor qualifies every optional
KITS, PLOCKS, Scenes or Loopback combination.

The subsequent `codex/harmony-cpu-20261026` branch optimizes Harmony on this
same integration. Its [CPU measurements](../modules/midi-harmony/DEVELOPMENT.md#cpu-optimization-2026-10-26)
compare executed ColdFire instructions, preserve persisted formats and separate
source, linked-firmware and full-port checks from physical hardware timing.
The [CPU validation receipt](harmony-cpu-validation-20261026.json) records the
tested source stages, image hashes, measured tradeoffs and declared skips.
