# MIDI Scales author-source review

This branch contains only MIDI Scales, its manifest and documentation. It is
a narrow source review for the matching `codex/pr/midi-scales` branch in
[radiohagen/octabam](https://github.com/radiohagen/octabam).

Source: radiohagen, original local Octabam commit
`03f7e81aee53d1d0b0c16ef1694bb10a35dcb63d`. The assembly is unchanged.
The manifest derives its assembly path from its own directory so Octabam can
build this pinned source as a submodule. Octabam owns the gate and its harness.

The full migrated source is on `main`. This independent review root deliberately
omits unrelated modules and the mixed development history. No firmware is included.
Hardware testing remains pending. See [module controls](modules/midi-scales/README.md).
