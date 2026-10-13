# POST FADER proof of concept

Maintained feature branch: `codex/modules/post-fader`. The original tested
prototype remains at `codex/poc/send-return-20261013` (`9b9e2060`). This
branch owns the optional module, its tests and its dedicated test remix.
It is not yet selected by the personal integrated release.

Extracted from sanderlegit's [PR 542](https://github.com/sambanks/octabam/pull/542),
head `2b4b0ed1b4c91e184c59994e352c194afc00b18a`, onto upstream
`fb5daa9766f1af1f61207c6baae056347a2edcd5` on 13 October 2026.
`postfader.s` is byte-for-byte the PR source. The manifest credits the PR
contributor and adds the current-image verification gate.

After stock builds the eight DSP records, scale each SEND/BusDelay/BusVerb
DEL and REV word by `(LEVEL/128)^2`, using the mixer snapshot after mute and
solo. A muted or excluded track publishes zero sends. Preserve BusDelay's
low REV byte because TEMPO SYNC uses it for a held note. Change only the
current DSP-bound record: the Part, parameter locks, panel values and other
FX parameters retain their original values.

This is opt-in through the `send-return-poc` test remix. Removing POST FADER
from a remix restores upstream behavior; there is no persistent setting or
new project format. It changes active sends' gain as well as mute behavior:
at LEVEL 55 the factor is about 0.185. It uses the MAIN LEVEL high byte;
it does **not** apply the separate scene crossfader XLV curve, CUE gain or
AMP VOL. Current USB AUDIO OUT's TRACKS POST implementation documents the
complete mixer calculation, which is more involved than this PR technique.
Do not describe this prototype as an exact tap of the post-mixer audio.

Mute stops new excitation, with the existing SEND smoothing and bus latency.
It does not reset either effect's state, so existing repeats and reverb tails
can decay. Shared tails cannot selectively identify which muted track made
them. This module does not separate T1/T5's returns: muting a host still
also mutes the shared return currently printed onto that host.

## Verification

- `tools/verify/verify_postfader_hook.py`: execute the installed detour in
  the built image, with a stubbed stock builder, over both buffers, all eight
  records and all LEVEL values. Check dirty fractions, the held-note byte,
  untouched records, mixer snapshot and registers.
- `tools/verify/verify_postfader.py`: execute the actual firmware builder
  and both DSPs on owned copies of a project. Compare muted and solo-excluded
  T7 with sends 100 versus 0; neither bus should change. Restore only the
  original call in a private control image; the muted-track change must then
  alter both hosts' output, excluding a silent/vacuous pass.

These are emulator checks, not hardware acceptance. A live mute-transition
recording, cue-only use, scene crossfader behavior and hardware timing remain
outside the proof. No card or user project is edited.
