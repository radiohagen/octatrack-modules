# Verification boundaries

Original completed source: `03f7e81aee53d1d0b0c16ef1694bb10a35dcb63d`.
Upstream base: `2d1cbcf471cf8b63e2279b3c372a6ebb47456a99`.
Selection: `harmony-track-bus`, BUILD 79, PGO disabled.

The prior completed run passed its general check and 24 dedicated suites.
The general run's 13 project-dependent skips were covered by those dedicated
suites. Its exact image SHA-256 was:

`98e809740dcb5411c6498cc1e1a7a48e052f1c44652b5c269b7ed13f154e6856`

[Historical source validation](../integration/source-validation.json) records
worker/source/emulator identities and corrected failures. Those are prior-run
results, not claims that copying source reran every test.
[Migration checks](../integration/migration-validation.json) report checks
performed on the new repositories and their precise limits.

Physical power-off recovery, device timing and hardware MIDI/audio remain
untested. No card transfer, firmware installation or new release is implied.
