# PR 542: send and return routing review

Review date: 13 October 2026. PR 542 is closed (12 October); its head is
`2b4b0ed1b4c91e184c59994e352c194afc00b18a`. Current upstream is
`fb5daa9766f1af1f61207c6baae056347a2edcd5`; it has 567 commits not in the PR,
and the PR has 90 not in upstream. This experiment starts from current
upstream. The personal integrated branch's SEND, BusDelay and BusVerb sources
match that upstream at inspection time (`b03f25e1`).

## Placement assessment

The RETURNS technique is useful for independent routing, but does not free
T1/T5's FX2 slots. Both engines still execute in those slots. Their wet audio
moves into separate buffers, then into T8 before its chain when MASTER TRACK
is on, or directly into MAIN when it is off. T1/T5's dry audio can then use
their own mute, level and cue without controlling everyone else's returns.

T8's FX2 becomes RETURNS (DLY/VRB return levels), replacing the stock DELAY
used for Echo Freeze in current BottleService. With MASTER TRACK off, the
returns bypass T8's FX1 and fader; current BottleService's USB MASTER layout
captures T8, not direct MAIN. That combination would need an explicit USB
routing decision. Removing RETURNS from T8 restores the old host-print path
in the proposal. A fully slot-free bus needs a different execution mechanism,
instance state and parameter transport; this PR does not provide it.

Current build machinery already supports per-payload DSP placement and
`DspHook`; the PR's old build-system changes are not a prerequisite.

Do not merge the old PR or overwrite the current engines:

- Current BusVerb has different feedback scratch assignments and current
  engines have the later interruptible-loop fixes. The old source would
  undo those changes. Current guidance also identifies DSP DMA contention
  that a lock-step emulator cannot rule out.
- RETURNS needs private Y state and shared delay-return buffers at
  `0x36200..0x36308`, an audited mixdown hook and cross-core handoff. Port its
  routing changes separately, declare ownership against the current ledger,
  preserve the modern engines, and recheck cycles, legacy bit identity,
  dirty state, master on/off, removal/reload and core skew before hardware.
  This current BottleService build has 207 free DSP program words on core A
  and 768 on core B; a new RETURNS build must demonstrate that it fits.
  The old PR reported a 149-word RETURNS body, before its engine additions.
- Current FX2 LOCK already protects all FX2 choosers at `0x400bc374`.
  The PR's HOST LOCK claims the same location. Carrying both is unnecessary
  and conflicts; selecting a new T8 return effect also needs a deliberate
  setup path under the current lock. RIG HOSTS currently stamps stock DELAY
  on T8, not RETURNS.
- Old Octakit/USB/remix assumptions are obsolete. Current BottleService uses
  KITS, STORE, PLOCKS P2 and the consolidated USB AUDIO OUT module.

## Muting assessment and implemented experiment

Current SEND receives DEL/REV before the track mixer mute. Its zero-knob
registration guard cannot tell that a track is muted. PR 542's POST FADER
hook is a small reusable fix at the DSP-record boundary; current upstream's
USB TRACKS POST independently documents the same mute/solo mixer snapshot.

The test remix is current BottleService plus POST FADER. All current DSP
sources, KITS, scene modules, release branches and user projects are unchanged.
See [the module](../../../modules/post-fader/README.md) for exact behavior
and limitations. In particular it stops new sends, preserves existing tails,
and applies LEVEL attenuation; it does not yet make host mutes independent
or implement RETURNS. The requested tail policy is decay, not hard cut.

## Reproduce

From this worktree, with its dependencies and stock image prepared:

```sh
make bus REMIX=send-return-poc
.venv/bin/python3 tools/harness/stress_project.py --remix send-return-poc --source /path/to/local/template --out out/poc-stress
.venv/bin/python3 tools/verify/verify_postfader_hook.py send-return-poc
.venv/bin/python3 tools/verify/verify_postfader.py send-return-poc --project out/poc-stress --image out/mainos_bus.bin
OT_PROJECT=out/poc-stress make check REMIX=send-return-poc MODULES='POST FADER'
```

The tests copy and normalize the template and generate local audio. They do
not establish device playback, recovery, or suitability for a firmware flash.

## Local results, 13 October 2026

- `make check REMIX=send-return-poc MODULES='POST FADER' OT_PROJECT=out/poc-stress`:
  PASS. This runs the shared floor, project boot/audio/USB checks and the
  reached bus gates; it is not every unrelated module's complete test suite.
- Installed-hook gate: 256 cases PASS, including both record banks, every
  LEVEL, preserved registers and delay held-note bytes.
- Six 1,000-frame firmware/DSP runs PASS. After warm-up, both hosts are
  bit-identical for muted and solo-excluded T7 sends at 100 versus 0
  (0/350 differing frames per host). With only the hook restored to stock,
  both hosts differ in 350/350 frames. All compared streams are non-silent.
- Current BottleService without POST FADER: project gate PASS using the
  same fixture. The shared gate now predicts scaled sends only for remixes
  selecting POST FADER; its original assertions remain for other remixes.
- The current personal integrated remix plus this module has no declared
  ledger conflicts (35 modules). This is a static composition check only;
  that personal image was not rebuilt or runtime-tested with the module.
- The extracted assembly source matches the PR exactly (SHA-256
  `e4d2364aa027eaa31521f590b951b4fbbfd9372ff30e6ba1e0a49b01a928dfe5`).

Logs and local test images are under this worktree's ignored `out/`.
RETURNS itself remains design-reviewed, not implemented. No flashable release
package, card transfer, upstream PR or remote push was made.
