# First three upstream contributions

Preparation against upstream `1915559f023518700406d5e6090a164e49c8e3e7`.
No upstream PR has been opened or merged.

| Contribution | Classification | Dependencies |
|---|---|---|
| [PLOCKS edit/release](pr/plocks-editor.md) | Existing correctness fix discovered during integration | None of the new MIDI modules |
| [TEMPO SYNC installed-hook gate](pr/tempo-hook-symbols.md) | Additional regression coverage; upstream already fixed the collision | No dependency for future feature merges |
| [MIDI Scales](pr/midi-scales.md) | Standalone feature | Its narrow, public author-source pin only |

Each candidate starts directly from the same upstream main. They can be
reviewed independently. Rebase and rerun the required reach checks if main
moves before submission. The full MIDI integration remains separate.

| Branch | Qualified commit | Result |
|---|---|---|
| `codex/pr/plocks-editor` | [`e7386633`](https://github.com/radiohagen/octabam/commit/e73866331bff84ad025d47beec3c20124c3ed9c3) | Required QUICK checks passed |
| `codex/pr/tempo-hook-symbols` | [`4aa321d4`](https://github.com/radiohagen/octabam/commit/4aa321d4f5ef1c429265b4951df4a4f24eeda611) | Required QUICK checks passed |
| `codex/pr/midi-scales` | [`16d8c7da`](https://github.com/radiohagen/octabam/commit/16d8c7daab86292a3a85573971613d03bec9261a) | Required QUICK checks passed |

[Exact commands, receipts and skips](../integration/pr-readiness.json).

PLOCKS fails on unchanged upstream and passes with the fix, including the
project-backed checks on all three official remixes. TEMPO retains upstream
firmware unchanged and adds coverage that detects the historical collision.
Scales verifies the installed paths, preserves the native source bytes, and
checks its pinned author reference on every build.

One initial TEMPO qualification run hit an existing USB packet-size failure.
An identical-firmware upstream control and the required rerun passed without
code changes. Its cause is undetermined; it is documented, not erased.

Hardware has not been tested. Passing the required quick tier is not a claim
of strict acceptance, every possible combination, or physical-device behavior.
The PR bodies list exact checks, skipped boundaries and provenance.
