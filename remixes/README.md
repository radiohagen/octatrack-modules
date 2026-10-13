# Remix selections

The imported selections keep their native Octabam names, settings and module
identifiers. They include the standard `mattias-bottleservice`, the separate
`mattias-sophie-poc`, and focused selections under `test/` for the MIDI modules,
Sophie and Post Fader. They are source definitions, not shipped firmware images.

Run them from the staged Octabam worktree. Their source commits and hashes are in
[sources.json](../integration/sources.json). The standard selection uses the MIDI
features and support modules, but does not select Sophie, Supersaw or Post Fader.
Importing those experiments does not make them enabled by default or qualify
mixed-engine playback. Keep each experiment's documented acceptance limits.
