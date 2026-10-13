# Modules

No modules have been migrated yet. Existing source and evidence remain in the
Octabam fork until a verified extraction is complete.

Each real module gets `modules/<slug>/` with `manifest.py`, `README.md`, its
source and focused checks. Document origin, licence, native behavior, dependencies,
resource claims, test results and hardware status. Use Octabam's schema rather
than introducing another manifest format.

Start with the [inactive template](_template/README.md). Keep shared platform code
in Octabam. Modules are selected at firmware build time, not loaded as plugins on
the physical instrument.
