# Musical Units integration

This package contains the display-only module, focused gates, stock-effects test
remix, player guide and 18 native-panel screenshots. The module README describes
its controls and custom-module helper ABI. Octabam owns the builder and shared
harnesses; the eight-file support patch adds descriptor validation, capture
coverage and manual/index entries to the exact baseline below.

Use this recipe for Musical Units. The Harmony/Follow integration pin and generic
historical staging workflow are separate. No other author modules are selected
by this test remix, and this evidence does not qualify a personal combined package.

## Reconstruct the verified source

The integration base is upstream Octabam
`3b3da30e1f36abed6202d46d5fc97a47a825b17f`. The local tested source commit is
`d9bf960b259833f4065fae8d849e547f9cdfad81`; it is not published in the Octabam
fork. All of its changed files are supplied here, either directly or in
[musical-units-octabam.patch](musical-units-octabam.patch). The
[validation receipt](musical-units-validation.json) names each file and its hash.
Record the exact author-repository commit used for a new build.

Create a clean, separate Octabam worktree at that base. From this author checkout,
set `octabam_tree` to the absolute path of the new worktree, then run:

```sh
module_repo=$(pwd)
python3 - "$module_repo" "$octabam_tree" <<'PY'
from pathlib import Path
import hashlib, json, shutil, subprocess, sys
source, target = (Path(p).resolve() for p in sys.argv[1:])
r = json.loads((source / 'integration/musical-units-validation.json').read_text())
def git(*args):
    return subprocess.check_output(['git', '-C', str(target), *args], text=True).strip()
assert Path(git('rev-parse', '--show-toplevel')).resolve() == target
assert Path(git('rev-parse', '--absolute-git-dir')).resolve() != Path(git('rev-parse', '--path-format=absolute', '--git-common-dir')).resolve()
assert git('rev-parse', 'HEAD') == r['integration_base']
assert not git('status', '--porcelain', '--untracked-files=all')
patch = source / r['support_patch']
assert hashlib.sha256(patch.read_bytes()).hexdigest() == r['support_patch_sha256']
subprocess.run(['git', '-C', str(target), 'apply', '--check', str(patch)], check=True)
for name in r['copy_files']:
    src, dst = source / name, target / name
    assert src.resolve().is_relative_to(source) and dst.resolve().is_relative_to(target)
    assert not src.is_symlink() and not dst.exists()
    assert hashlib.sha256(src.read_bytes()).hexdigest() == r['validated_files'][name]['sha256']
for name in r['copy_files']:
    dst = target / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / name, dst)
subprocess.run(['git', '-C', str(target), 'apply', str(patch)], check=True)
for name, record in r['validated_files'].items():
    assert hashlib.sha256((target / name).read_bytes()).hexdigest() == record['sha256'], name
print('Reconstructed all 35 changed files with their validated bytes.')
PY
```

Initialize Octabam's submodules and follow its toolchain/stock-firmware setup.
Do not reuse another worktree's emulator build. From the integration worktree:

```sh
make check REMIX=musical-units MODULES='MUSICAL UNITS'
.venv/bin/python tools/site/capture_manual.py musical-units --project /path/to/disposable-source-project
.venv/bin/python tools/verify/verify_musical_units_port.py
```

The capture tool copies the supplied project into its own disposable fixture.
No firmware, sample or device project is supplied by the author repository.

## Recorded verification

The exact source passed the scoped composed-image suite, 21,000 formatter calls,
1,324 native-font label-width checks, native LFO phase/tick probes, documentation
checks and 18 panel captures. Held audio and MIDI trig labels have pixel assertions.
The imported source is byte-identical; publication does not change firmware code.
The receipt records separate shipping/capture image hashes and the log hashes.

The suite's project-backed `verify_set` was skipped because no `OT_PROJECT` was
provided. The screen/timing fixture ran separately; it does not qualify sample
playback, a user's live project, other remixes or physical hardware. Source checks
in this repository are additional packaging checks, not firmware acceptance.
