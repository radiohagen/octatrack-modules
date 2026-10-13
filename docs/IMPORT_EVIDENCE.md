# Source import evidence — 2026-10-13

This records the original import at `563040a7764b9b1e79febf08113d0931fc0c527d`.
Later naming changes are recorded in [the rename evidence](MIDI_ARP_RENAME.md).
The original paths and hashes below remain historical evidence.

## What was imported

Eight feature modules and four supporting modules, listed in the
[catalogue](../modules/README.md), plus their generators, checks and native remix
selections. The import contains 230 original files: 226 are byte-identical to
source; four Markdown files change only the feature name or links to external
Octabam documents. External documentation links use the accessible published
reference `94fa3cdcb893c4f48a15533f1a49ea3546d7d12f`; this does not change the
local integration pin. All executable source, manifests, generators and gates are
byte-identical to their recorded origin. Sophie retains the exact upstream
submodule pin.

The main source snapshot is `mattiaswolff/octabam` at
`3bd99bca5d44ae6257112747070be77fef110839`; Post Fader is imported from
`0f45b499464e65092f7cfa652012c0695943a5cf`. Original paths and SHA-256 hashes
are in [sources.json](../integration/sources.json). These are exact source
snapshots, not an assertion that every feature branch has the same history.
The main integration commit exists locally but was not resolvable through GitHub
during import; the Post Fader commit was resolvable. No private integration history
was published. See the local-worktree setup in the integration guide.

At import, **MIDI Arp Presets** was a display-name correction only; the original
build selector was `ARP PRESETS`. The subsequent rename updates code paths and
selectors too; see the rename evidence above.

## Build identity

A fresh isolated Octabam worktree at the pinned main snapshot built the standard
selection before and after source staging:

```
make bus REMIX=mattias-bottleservice BUILD=84
cmp out/import-baseline.bin out/mainos_bus.bin
```

Both builds passed. The MAIN OS files are byte-identical, 1,180,638 bytes:

```
95bfbd3b7da5d81f42d7adeab2a3ced2d1d69ba05694b16daba5b6598b3f1d21
```

The standard selection includes the MIDI features and supporting modules. It does
not select Sophie, Supersaw or Post Fader; this image comparison does not qualify
those experiments or their combinations. No binary is committed here.

## Verification scope

Repository checks include source syntax, file links, module layout, the pinned
integration record and 12 unit tests. Staging was exercised against the isolated
worktree; tests also reject primary checkouts, wrong revisions, dirty targets and
escaping paths. The helper copies source only and does not change an active build.

Focused results are recorded in [import-evidence.json](../integration/import-evidence.json).
The full
project/RTOS acceptance suite, external-author adapters, and physical hardware
acceptance are outside this import. Historical results in module READMEs remain
historical and are not silently promoted to new evidence.

Existing sources, integrated packages and device state remain unchanged. The
repository is ready for source development with isolated staging. Making it the
external module source used by ongoing Octabam builds still requires adapter
extraction and final integration checks.

## Focused results

Eleven focused checks passed against the staged standard configuration: MIDI Arp
Presets, MIDI Scales, Part access, Part copy, Part settings, MIDI SRAM, MIDI Follow,
MIDI Loopback, Loopback/Scenes, and the Sophie and Supersaw host checks.
The MIDI Follow project/RTOS portion was explicitly skipped because no project
fixture was supplied; this result covers its linked-code portion only.

The initial exhaustive Harmony check exceeded a 120-second bound. A subsequent
unmodified run against the dedicated `harmony-plocks` selection passed in 452.13
seconds, including all scale/key/pitch combinations, voicing, inversion, omitted
notes, root placement, spread, recorder handoff, live transpose and controls.

The Harmony/PLOCKS gate failed with an unmapped-memory write on the standard
shared-pool configuration. It passed on the intended `harmony-plocks` selection
with CONTIGUOUS retention, including full capacity, copies/undo, saves/backups,
failure guards and new-project initialization. The initial failure is retained
in the receipt. This does not qualify that harness on the shared-pool image;
the standard image comparison remains a separate, successful check.

Sophie and Supersaw results here are host/generator/bridge checks, not experimental
full-image or physical capacity qualification. All original limits remain.
Hosted Actions again failed to start any steps because of the account billing /
spending restriction. Local source checks passed independently.

Post Fader also built with `make bus REMIX=send-return-poc BUILD=P1` and passed
`.venv/bin/python tools/verify/verify_postfader_hook.py send-return-poc`:
256 installed-hook cases covering buffers/tracks, levels, dirty fractions,
held-note preservation, non-send records and registers. Its audio-project gate
was not run during this import. The image hash is in the machine-readable receipt.
