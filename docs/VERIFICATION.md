# Verification

## Source checks

`make check` validates tracked Python syntax, the Octabam reference pin, module
layout, relative Markdown file links and the absence of common binary artifacts.
It runs the repository's unit tests. CI runs this same command using Python 3.12.
The artifact check is a hygiene guard, not a detector of every possible firmware
encoding. Review staged files before publishing.

## Firmware checks

Once modules are imported, use the pinned Octabam tools and its contribution
requirements. Run both focused module gates and the intended combined remix.
Check hooks, resource claims, native disabled behavior and interactions with
KITS, Scenes and other selected modules where applicable. Validate UI changes
through the actual port-rendered display.

For a pure extraction, compare image hashes before and after using the same
Octabam commit, stock input, toolchain, fixture and selection. Path text in a
report can change without changing an image; account for it explicitly.

## Evidence record

Keep a short record beside the module, linking larger local reports as needed:

- Source repo and full commit; Octabam repo and full commit.
- Selected remix and exact module versions.
- Fixture identity/hash and stock input hash, without uploading their contents.
- Commands, results, report references and generated image hash.
- Known failures, skipped checks and their implications.
- Hardware model, actual flashed image, test date and observations if tested.

Report source, emulator, packaged image, card copy, OS upgrade and physical
behavior separately. A successful build or card copy never proves playback.
Earlier hardware evidence applies to the tested image and cases only.
