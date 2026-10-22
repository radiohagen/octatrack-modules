# Integration developer notes

Follow [the current adapter workflow](README.md) for Harmony/Follow.
The older native staging and N1 package recipes remain in Git history.
Do not copy those recipes over the shared-event adapter checkout.

Source records preserve the original file SHA-256 and also the published hash
where documentation links were made portable. Never silently advance pins.

`make check` also verifies published source hashes and executable modes.
For a deliberate source edit, update `published_sha256` in the same reviewed
change and retain the original `commit`, `path` and `sha256` provenance.
New files created in this author repository use `origin: authored` and an
explicit repository URL instead of claiming an imported source commit.
Their history is tracked by Git; their current bytes and modes are checked by
the same receipt verifier.
