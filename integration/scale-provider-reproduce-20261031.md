# Scale provider verification replay

The adjacent JSON receipt records the tested source hashes, commands, artifact identities and limits. No firmware, private project, emulator binary or MIDI capture is bundled.

The firmware qualification used the locally preserved Octabam integration `8ea12be073d0211f42c2d6990ab9a07a7b47aee1`, descended from upstream `645f964f`. This is a composed integration baseline, not a claim that the author source applies directly to upstream. The baseline has no remote-containing ref in the inspected checkout. Preserve it when replaying these exact results.

In an isolated checkout of that baseline:

1. Initialize its pinned dependencies and use the existing supported Octabam toolchain. Supply an authorized raw firmware dump at `out/raw/section_3_MAIN_OS.bin`.
2. Apply `integration/scale-provider-integration-20261031.patch` from this author repository. Its five small test remixes and `midi_machine.py` bridge were checked against the exact baseline with a disposable Git index.
3. Copy each file named in `reproduction.author_verifiers_to_copy` in the JSON receipt from this author checkout to the same relative path in Octabam. The 38 historical helper files already exist in this author repository; historical local commit `4316bd1` is provenance, not a replay dependency. The new scale gate is the 39th file.
4. In each private `modules/midi-follow/upstream` and `modules/midi-harmony/upstream` checkout, copy this author's `modules/midi-follow` and `modules/midi-harmony` source directories, plus `integration/pitch_response.py`, `scale_provider.py`, `scale_key.s` and `scale_math.s`. Use the JSON's staged-source hashes to check the tested snapshot. This intentionally tests local working source before a new author pin exists.
5. Build the selected fixture and run the exact commands in the JSON. For example:

```sh
REMIX=harmony-follow-review XBUS=1 SPEC=1 .venv/bin/python tools/build/build_bus.py
.venv/bin/python tools/verify/verify_midi_scale_provider.py harmony-follow-review
.venv/bin/python tools/verify/verify_midi_pitch_response.py harmony-follow-review --expect-harmony present
```

Use `midi-follow`, `midi-follow-scales-provider`, `harmony-review`, `harmony-scales-provider` and `harmony-follow-native-review` for the other five recorded compositions. Build and test one image at a time; the gates read the current `out/` artifacts. The receipt preserves their identities independently.

The six full-firmware UART comparisons additionally require the private native project fixture and original local comparison receipt named in the JSON. They are excluded here. Build a source-matched private emulator with `OCTABAM_PGO=0 .venv/bin/python tools/emu/port_store.py install` before running those captures. A different fixture or baseline cannot establish equality with the recorded event sequences.

Standalone Follow stock/MS instruction budgets pass (79/143 cases). Combined budgets remain unmet: the original pinned combined control already fails 53/143, and the provider candidate fails 54/143. The receipt reports the measured cost separately; no budget was relaxed. All functional/lifecycle assertions pass. Harmony's broad inversion sweep was stopped after the listed relevant checks; it is not recorded as a complete Harmony script pass. No hardware or card acceptance is implied.
