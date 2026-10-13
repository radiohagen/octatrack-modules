# Module template — inactive

Copy this directory to a descriptive module slug. Start the actual manifest from
the closest working module at the pinned Octabam revision; use its DSP or ColdFire
template only when there is no closer analogue. Do not invent hook addresses or
claims to fill out a template. This folder intentionally has no executable manifest.

Replace this README with:

1. User-visible behavior and controls, including disabled/native behavior.
2. Source provenance: original repo, commit, paths, authors and licence.
3. Implementation boundaries, hook/resource claims and interacting modules.
4. How to run the focused gates and which combined remix to check.
5. Current results, exact source/build identity and known limitations.
6. Hardware status, with image/model/date if physically tested.

Keep assembly/C source, generator inputs and generated assembly together where
the established module needs them. Derive paths from the manifest's location.
Use module-owned tests where practical; retain necessary Octabam gate adapters.
