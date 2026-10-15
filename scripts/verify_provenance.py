"""Verify published source against its receipt without changing origin hashes."""
from pathlib import Path
import hashlib
import json
import stat

ROOT = Path(__file__).resolve().parents[1]


def verify(root: Path, receipt: dict) -> list[str]:
    root = root.resolve()
    errors = []
    for name, entry in receipt['files'].items():
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
            errors.append(f'{name}: missing, symlinked or outside source root')
            continue
        expected = entry.get('published_sha256', entry['sha256'])
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            errors.append(f'{name}: published bytes differ from receipt')
        expected_mode = entry.get('source_mode')
        actual_mode = '100755' if path.stat().st_mode & stat.S_IXUSR else '100644'
        if expected_mode and actual_mode != expected_mode:
            errors.append(f'{name}: executable mode differs from receipt')
    return errors


def main() -> None:
    receipt = json.loads((ROOT / 'integration/sources.json').read_text())
    errors = verify(ROOT, receipt)
    if errors:
        raise SystemExit('\n'.join(errors))
    print(f"Provenance: {len(receipt['files'])} published source files match hashes and modes.")


if __name__ == '__main__':
    main()
