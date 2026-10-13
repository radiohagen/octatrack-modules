# Repository tools

`check.py` implements source-only checks used by `make check` and GitHub Actions.
It checks tracked files, so add new files to the index before running it locally.
It performs no downloads, firmware build, device access or changes to Octabam.

Do not copy Octabam's builder, schema or emulator into this directory.
