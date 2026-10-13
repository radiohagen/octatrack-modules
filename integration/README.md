# Octabam integration

[octabam.json](octabam.json) records the exact upstream revision selected as the
initial reference. It is a reference for extraction, **not a firmware compatibility
certification**. No modules have been integrated or built from this repository yet.
When migration requires a fork commit, update both repository and commit explicitly
and record the reason in the PR.

## Prepare the builder

Use a separate Octabam checkout/worktree at the recorded commit. For example,
clone `https://github.com/sambanks/octabam.git` into a sibling working directory,
check out the exact commit from octabam.json, read its AGENTS.md, and follow its
setup instructions. Initialise the required submodules. Supply your own stock OS
and project fixtures locally. Do not repoint an active integration checkout.

## Import a migrated module

Follow Octabam's existing pattern: an author repo pinned under
`modules/<slug>/upstream` and a small `modules/<slug>/manifest.py` that executes
the author's declaration. The source declaration here lives at
`upstream/modules/<slug>/manifest.py`.

Once that module exists, the adapter takes this form (replace `<slug>`):

```python
from pathlib import Path
import runpy

source = Path(__file__).resolve().parent / "upstream" / "modules" / "<slug>" / "manifest.py"
MODULE = runpy.run_path(str(source), run_name="author_module")["MODULE"]
```

The author's manifest resolves source paths from its own `__file__`, so moving
the checkout cannot silently select another copy of the source. Gate paths must
satisfy Octabam's schema: currently repo-relative under `modules/` or `tools/`.
Check gate execution and imports as part of extraction; a source path fix alone
does not relocate the test harness. Preserve the module's native key and claims.

This repository is private. Anyone consuming its submodule needs access; a public
upstream PR must not acquire an inaccessible private dependency. Initially keep
the integration in the owner's fork. Choose publication or an agreed source
contribution before proposing adoption by public upstream.

## Check and promote

Run the module-only selection and the actual combined remix with Octabam's
`make check REMIX=<name>` and applicable contribution gates. Record both repo
commits and the built image hash. Keep fixtures and outputs out of Git.
The normal hosted CI here does not have firmware or build the firmware.

Advance the integration pin deliberately after a module PR merges. A pin update
is reviewable on its own and includes verification on the new pair of commits.
