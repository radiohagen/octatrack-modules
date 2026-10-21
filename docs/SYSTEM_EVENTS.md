# Shared system events

The shared-event platform replaces HARMONY FOLLOW and HARMONY PLOCKS.
Octabam owns the two platform modules, following STORE's build-time client tables.
This source repository owns the HARM and Follow callbacks and musical policies.

- SEQUENCER EVENTS publishes transport start/resume and accepted MIDI output.
  HARM and Follow each receive notifications directly; EUCLID is another client.
- EDIT EVENTS selects a held-step editor by context and notifies side-data owners
  before and after native pattern/track copies, including clipboard and undo.
  HARM and PLOCKS P2 register independently. Native copying executes once.

Selections must include SEQUENCER EVENTS for Follow, and both platform modules
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
