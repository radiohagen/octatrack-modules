# Shared system events

## Current MIDI Follow

Follow uses upstream **EVENTS**, merged in Octabam #871. It subscribes to
`transport.start`, `transport.resume` and `midi.note_accepted`; the platform
preserves native registers and owns each firmware hook once. See the
[current integration](../integration/midi-follow.md). The legacy combined
integration below must keep its recorded source pin.

## Current Harmony migration

Harmony also uses **EVENTS** for transport, accepted MIDI output, held-step
ownership and `edit.copy_pre` / `edit.copy_post`. Post-copy callbacks observe
the completed native copy; the platform preserves its output registers and CCR.
STORE dispatches Harmony's load, retained-memory and new-project lifecycle.
Its optional checked callbacks can refuse bank writes/copies and propagate
companion-copy failures. Existing saved formats and retained allocations stay
unchanged. See [the migration review](../integration/harmony-current.md).

## Historical combined integration

The shared-event platform replaces HARMONY FOLLOW and HARMONY PLOCKS.
Octabam owns the two platform modules, following STORE's build-time client tables.
This source repository owns the HARM and Follow callbacks and musical policies.

- SEQUENCER EVENTS publishes transport start/resume and accepted MIDI output.
  HARM and Follow each receive notifications directly; EUCLID is another client.
- EDIT EVENTS selects a held-step editor by context and notifies side-data owners
  before and after native pattern/track copies, including clipboard and undo.
  HARM and PLOCKS P2 register independently. Native copying executes once.

Those historical selections include SEQUENCER EVENTS for Follow, and both platform modules
for HARM. Remove HARMONY FOLLOW and HARMONY PLOCKS from existing selections.
Their implementations are retired; Git history preserves the previous versions.
STORE remains responsible for project and Part persistence. No saved format or
retained allocation changes as part of this migration.

Transport callbacks do not perform note transformations. With HARM OFF, Follow
receives effective native N1–4. With HARM NOTE/CHORD, it receives the resolved
root; the follower generates its own voicing. Those rules stay in the clients.

The platform READMEs in Octabam define callback registers, ordering, context
ownership and native continuations. Full validation is required on the matching
Octabam integration; source checks alone do not establish firmware behavior.
