# MIDI Arp Presets naming — 2026-10-13

The module now uses `MIDI ARP PRESETS` as its build selector,
`midi-arp-presets` as its module and standalone-remix name, and
`verify_midi_arp_presets.py` / `verify_midi_arp_presets_port.py` as its gates.
The linked unit is `midiarppresets`. Documentation uses **MIDI Arp Presets**.

This replaces the old selector `ARP PRESETS` and slug `arp-presets`.
External remix selections and commands must adopt the new names when importing
this revision. There is no second compatibility module with duplicate hooks.
Native ARP SETUP, compact rhythm titles, presets and playback logic are unchanged.

The source receipt maps current file names to their original paths and hashes.
Staging into the pinned, clean Octabam worktree removes only the tracked original
files replaced by these renames, preventing discovery of duplicate modules.
Historical import results remain in [IMPORT_EVIDENCE.md](IMPORT_EVIDENCE.md).
This revision does not switch existing firmware checkouts or update a device.

## Verification

Checked in an isolated Octabam worktree at the integration pin
`3bd99bca5d44ae6257112747070be77fef110839`, using the same stock input and
compiler as the original import. No runtime C or hook assembly changed.

- `make check` in this repository: passed, 261 tracked entries, 12 manifests,
  13 tests, including rename staging and rejection of untracked/escaping originals.
- `generate.py --check`: passed; generated assembly differs only in source paths.
- Staging: passed, 229 files copied and ten tracked original paths retired.
- Built the original `arp-presets` and renamed `midi-arp-presets` selections
  with `BUILD=84`: byte-identical, 1,114,097 bytes, SHA-256
  `255ee28f9129dcc9b72e292eaff39b7d004726661d4ae8819604695a9fe9229c`.
- Built `mattias-bottleservice` before and after staging with `BUILD=84`:
  byte-identical, 1,180,638 bytes, SHA-256
  `95bfbd3b7da5d81f42d7adeab2a3ced2d1d69ba05694b16daba5b6598b3f1d21`.
- `verify_midi_arp_presets.py` passed on both selections: all 96 speed values,
  1,088 preset applications, boundaries, ABI, titles and stock editor comparisons.
- Native gate discovery lists both renamed gate paths under `MIDI ARP PRESETS`.
- The full-port panel/save/MIDI gate explicitly skipped: no project fixture supplied.
  No full firmware acceptance suite or hardware test is claimed for this rename.

The pinned Octabam builder still has the historical test-remix name in its shared
selftest's harvest expectation table, and generated module indexes name the old
module. Update that table and regenerate builder documentation when adopting the
rename in Octabam. Those shared builder files are outside this author repository;
external-adapter migration and full integration acceptance remain separate work.
Historical releases and import receipts intentionally retain their original names.
