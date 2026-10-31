# Harmony on current EVENTS and STORE

## Scale provider boundary

Follow and Harmony bind scale requests through the integration layer. A provider
owns scale selection and storage; the consumers own source routing, Part context,
generated notes and releases. Adding a provider requires an adapter and its
compatibility checks, without putting its module name or catalogue IDs into
Follow or Harmony. The existing stock and MIDI Scales paths remain the reference
for their respective note-correction rules.

Harmony retains its current saved format and the seven existing diatonic modes:
Ionian, Dorian, Phrygian, Lydian, Mixolydian, Aeolian and Locrian. This does not
include harmonic or melodic minor merely because they also have seven notes.
A Harmony-compatible adapter must preserve that restriction. Unsupported scales
must not be substituted with Major/Minor or interpreted as stored mode IDs.
Composition rejects an adapter whose declared catalogue includes unsupported
masks; the adapter must enforce that catalogue when loading or editing scales.

The adapter contract is in [scale_provider.py](scale_provider.py). Reads take a
resolved local track and an explicit working or saved Part context, and return a
tonic plus pitch-class mask. The binding declares its finite mask set and whether
it owns KEY display/editing. A provider with its own storage must supply a KEY
formatter that reads its own context, rather than interpreting Harmony's native
display byte. It must also resolve inherited Follow display values and keep all
editing paths, including any chooser, read-only on followed tracks. These are
adapter qualification requirements; declaring a mask set alone is insufficient.

The unmodified [SCALES prototype](https://github.com/Djibdjib/octabam/tree/feat/scales)
at `e4fbba56d098cf79909212991609df906bf82646` is incompatible. Its extended scale
ID occupies native MIDI SETUP byte 18, already used for Harmony CHRD/SIZE.
Its encoder/output hooks also need Follow inheritance and Harmony output
ownership support. A provider adapter cannot repair those ownership conflicts.
This combination is refused until the provider supplies compatible storage and
hooks. Existing Harmony projects keep their byte assignments; untagged prototype
SCALES data cannot be distinguished from Harmony settings by its value alone.

The earlier integration and validation records below apply only to their named
commits. Source checks, linked-code checks and complete firmware captures are
separate evidence; none establishes physical hardware behavior.

The [31 October validation receipt](scale-provider-validation-20261031.json)
records six stock/MIDI Scales compositions, explicit-Part and persisted-format
checks, and six complete UART comparisons. Standalone Follow instruction budgets
pass; combined budgets remain unmet in both the original-pin control and this
candidate, with measured differences recorded separately. The
[replay notes](scale-provider-reproduce-20261031.md) identify the locally preserved
Octabam base and the small support patch. This does not advance the older package
pin or qualify the SCALES prototype.

## Earlier integration

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
