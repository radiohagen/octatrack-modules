# Working in octatrack-modules

This is the author repository for Mattias's Octatrack modules. Octabam owns the
builder, schema, shared emulator and toolchains. Read README.md, CONTRIBUTING.md
and integration/README.md before firmware work. The initial repository contains
structure only; do not claim that it contains or validates migrated modules.

- After bootstrap, work in a separate Git worktree on `codex/<module>-<change>`.
  Never stash or edit another task's checkout. Preserve existing branches and evidence.
- Keep one module under modules/<slug> with source, manifest.py and README.md.
  Start from the nearest real Octabam analogue. `_template` is not executable.
- Use Octabam's existing schema and claims. Do not introduce a second module API,
  discovery mechanism, firmware packer or copied toolchain.
- Derive source paths from the manifest location. Keep gates module-owned where
  possible; gate paths must satisfy the pinned Octabam schema.
- Verify extracted modules against their original commit before changing behavior.
  Preserve authorship, licensing and source/proof provenance.
- Run `make check`. Firmware changes additionally require focused module gates,
  the intended combined remix and applicable Octabam contribution gates on the
  same source snapshot. Follow AGENTS.md in the Octabam integration worktree.
- Never equate source checks, emulator checks, packaging, card copy and hardware
  acceptance. Record exact commits, image hash, fixture and remaining uncertainty.
- Keep stock firmware, generated firmware, project files, samples, caches and
  private device material out of Git. Use ignored artifacts/ for local output.
- No destructive cleanup or migration of existing work without explicit authority.
  Moving a module is separate from approving a firmware behavior change.
- Prefer Python's standard library and small existing patterns. Check actual
  rendered UI when editing controls or layout. Preserve native behavior where required.
