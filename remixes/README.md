# Remix selections

This directory is reserved for our documented module selections and combined
acceptance cases. No remix is defined yet. Existing working selections stay in
the Octabam fork during migration.

When adding one, use Octabam's native `remix.py` schema and a README beside it.
Document the exact module pins and integration steps. Octabam discovers remixes
inside its own tree; placing a selection here alone does not install it there.
Run the shared builder and checks from the prepared Octabam integration worktree.
