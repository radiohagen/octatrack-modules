"""Source-only repository checks; never build or execute firmware modules."""
from __future__ import annotations

import ast
import datetime
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {'.bin', '.syx', '.elf', '.o', '.wav', '.aiff', '.flac'}
LOCAL_ONLY = {'artifacts', 'out', 'vendor', 'downloads', '.venv', '.worktrees'}
LINK = re.compile(r'(?<!!)\[[^\]\n]+\]\(([^)\s]+)(?:\s+"[^"]*")?\)')


def check_pin(path: Path) -> list[str]:
    try:
        pin = json.loads(path.read_text())
        if not isinstance(pin, dict):
            return ['Octabam pin must be a JSON object']
        errors = []
        if not re.fullmatch(r'https://github\.com/[\w.-]+/[\w.-]+\.git',
                            str(pin.get('repository', ''))):
            errors.append('Octabam repository must be an explicit GitHub HTTPS Git URL')
        if not re.fullmatch(r'[0-9a-f]{40}', str(pin.get('commit', ''))):
            errors.append('Octabam commit must be a full SHA, not a moving branch or tag')
        if pin.get('status') not in {'reference-only', 'integration-verified'}:
            errors.append('Octabam pin needs an explicit verification status')
        if not isinstance(pin.get('note'), str) or not pin['note'].strip():
            errors.append('Octabam pin needs a note explaining its scope/evidence')
        datetime.date.fromisoformat(pin['recorded_on'])
        return errors
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f'Invalid Octabam pin: {exc}']


def check_files(root: Path, paths: list[str], gitlinks: frozenset[str] = frozenset()) -> list[str]:
    errors = []
    names = set(paths)
    modules = set()
    for name in paths:
        # Git stores a submodule as a pinned commit, not as a regular file.
        # Its contents are checked in the integration workspace, not traversed here.
        if name in gitlinks:
            continue
        relative = PurePosixPath(name)
        path = root / name
        if relative.suffix.lower() in FORBIDDEN or relative.parts[0] in LOCAL_ONLY:
            errors.append(f'{name}: generated/private artifact must not be tracked')
            continue
        if path.is_symlink():
            errors.append(f'{name}: tracked symlink needs explicit review; use real source files')
            continue
        if not path.is_file():
            errors.append(f'{name}: tracked file is missing')
            continue
        if relative.suffix == '.py':
            try:
                ast.parse(path.read_text(), filename=name)
            except (SyntaxError, UnicodeError) as exc:
                errors.append(f'{name}: {exc}')
        if relative.suffix == '.md':
            # File targets only: no network calls or claims about remote URLs/anchors.
            for target in LINK.findall(path.read_text()):
                parsed = urlsplit(target.strip('<>'))
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                destination = (path.parent / unquote(parsed.path)).resolve()
                if not destination.is_relative_to(root.resolve()) or not destination.exists():
                    errors.append(f'{name}: broken/outside relative link {target}')
        if len(relative.parts) > 2 and relative.parts[0] == 'modules':
            slug = relative.parts[1]
            if not slug.startswith(('_', '.')):
                modules.add(slug)
    for slug in sorted(modules):
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
            errors.append(f'{slug}: use a lowercase hyphenated module slug')
        for required in ('README.md', 'manifest.py'):
            if f'modules/{slug}/{required}' not in names:
                errors.append(f'modules/{slug}: missing tracked {required}')
    return errors


def main() -> int:
    result = subprocess.run(['git', 'ls-files', '--stage', '-z'], cwd=ROOT, check=True,
                            capture_output=True)
    entries = result.stdout.decode().rstrip('\0').split('\0') if result.stdout else []
    paths = [entry.split('\t', 1)[1] for entry in entries]
    gitlinks = frozenset(entry.split('\t', 1)[1] for entry in entries
                         if entry.startswith('160000 '))
    if not paths:
        print('No tracked files. Add source files to the Git index first.', file=sys.stderr)
        return 1
    errors = check_files(ROOT, paths, gitlinks) + check_pin(ROOT / 'integration/octabam.json')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    count = len({PurePosixPath(p).parts[1] for p in paths
                 if p.startswith('modules/') and p.endswith('/manifest.py')
                 and not PurePosixPath(p).parts[1].startswith(('_', '.'))})
    print(f'Source checks passed: {len(paths)} tracked files; {count} module manifests.')
    print('Firmware builds, compatibility and hardware behavior were not checked.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
