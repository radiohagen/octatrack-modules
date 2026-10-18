"""Stage imported source into a clean, isolated Octabam worktree; never build."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def validate_target(target: Path, commit: str) -> None:
    target = target.resolve()
    if Path(git(target, 'rev-parse', '--show-toplevel')).resolve() != target:
        raise ValueError('Target must be the worktree root')
    own = Path(git(target, 'rev-parse', '--absolute-git-dir')).resolve()
    common = Path(git(target, 'rev-parse', '--path-format=absolute', '--git-common-dir')).resolve()
    if own == common:
        raise ValueError('Refusing a primary checkout; create an isolated Git worktree')
    if git(target, 'rev-parse', 'HEAD') != commit:
        raise ValueError('Target HEAD does not match integration/octabam.json')
    if git(target, 'status', '--porcelain', '--untracked-files=all'):
        raise ValueError('Target has local changes; use a fresh worktree')


def plan(source: Path, target: Path, receipt: dict) -> list[tuple[Path, Path]]:
    source, target = source.resolve(), target.resolve()
    pairs = []
    for name, record in receipt['files'].items():
        if record.get('stage') is False:
            continue  # historical shared helpers are owned by the builder
        if not name.startswith(('modules/', 'tools/verify/', 'remixes/')):
            continue  # licence copies and provenance stay in the author repository
        src, dst = source / name, target / name
        if not src.resolve().is_relative_to(source) or not dst.resolve().is_relative_to(target):
            raise ValueError(f'Path escapes its workspace: {name}')
        if not src.is_file() or src.is_symlink() or dst.is_symlink():
            raise ValueError(f'Expected regular source file: {name}')
        if dst.exists() and not dst.is_file():
            raise ValueError(f'Destination is not a file: {name}')
        pairs.append((src, dst))
    if not pairs:
        raise ValueError('No source files selected')
    for name, pin in receipt['submodules'].items():
        expected = f"160000 {pin['commit']} 0\t{name}"
        if git(target, 'ls-files', '--stage', '--', name) != expected:
            raise ValueError(f'Target submodule pin differs: {name}')
    return pairs


def retired_paths(target: Path, receipt: dict) -> list[Path]:
    """Retire recorded removals/renames, never unrelated or untracked content."""
    target = target.resolve()
    retired = []
    originals = set(receipt.get('retired_files', {}))
    for name, record in receipt['files'].items():
        if record.get('stage') is False:
            continue
        old = record['path']
        if old == name or not name.startswith(('modules/', 'tools/verify/', 'remixes/')):
            continue
        originals.add(old)
    for old in sorted(originals):
        path = target / old
        if (not old.startswith(('modules/', 'tools/verify/', 'remixes/'))
                or not path.resolve().is_relative_to(target) or path.is_symlink()
                or old in receipt['files']):
            raise ValueError(f'Invalid original path for rename: {old}')
        tracked = git(target, 'ls-files', '--', old) == old
        # A newly authored file may never have existed at the integration pin.
        if not tracked and not path.exists():
            continue
        if not tracked:
            raise ValueError(f'Original rename path is not tracked: {old}')
        if not path.is_file():
            raise ValueError(f'Expected regular retired file: {old}')
        retired.append(path)
    return retired


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--octabam', required=True, type=Path)
    parser.add_argument('--apply', action='store_true', help='copy after every guard passes')
    args = parser.parse_args()
    pin = json.loads((ROOT / 'integration/octabam.json').read_text())
    receipt = json.loads((ROOT / 'integration/sources.json').read_text())
    if receipt['integration_commit'] != pin['commit']:
        raise SystemExit('Source receipt and integration pin disagree')
    try:
        validate_target(args.octabam, pin['commit'])
        pairs = plan(ROOT, args.octabam, receipt)
        retired = retired_paths(args.octabam, receipt)
        changed = sum(not dst.exists() or src.read_bytes() != dst.read_bytes()
                      for src, dst in pairs)
        print(f'{len(pairs)} source files; {changed} differ; {len(retired)} original paths retired.')
        if args.apply:
            validate_target(args.octabam, pin['commit'])
            for src, dst in pairs:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            for path in retired:
                path.unlink()
            print('Source staged. Review the target diff and run its required gates.')
        else:
            print('Inspection only. Add --apply to stage; no files changed.')
    except (ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == '__main__':
    main()
