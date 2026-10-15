# Initialize all KITS record-header fields

Native Kit record initialization clears only the first eight header bytes, leaving flags and reserved fields dependent on prior allocator contents. Clear the remaining eight bytes and assert that every migrated or empty record has zeroed reserved fields.

Base: upstream `2d1cbcf471cf8b63e2279b3c372a6ebb47456a99`. Candidate branch: `codex/pr/kits-header`.
This prerequisite is independent of the new MIDI feature modules.

## Validation

The branch builds and its docs check passes. The direct linked initializer test
(`verify_kits_header.py`) clears all 256 deliberately dirty record headers and
preserves adjacent Part bytes. Unmodified upstream fails the same test with all
256 headers dirty, demonstrating the regression independently of zero-filled
fixtures.

The full KITS project verifier has three recall-counter failures (`progchg`,
`trackbtn1`, `extplay`). Unmodified upstream has the exact same failures using
the same verifier and inputs. This branch is **held for broader qualification**;
the focused pass does not mean the full suite passed. No upstream PR is open.
Rebase and run `make reach RUN=1 KEEP=1` before submission. Hardware is untested.
