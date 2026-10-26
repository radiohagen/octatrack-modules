"""Firmware-free Sophie engine specialization and adapter regression checks."""
from pathlib import Path
import hashlib
import json
import runpy
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class SophieTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'C compiler required')
    def test_adapter_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / 'sophie-test'
            subprocess.run([
                'cc', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
                '-fsanitize=address,undefined',
                '-fno-sanitize-recover=all',
                str(ROOT / 'modules/sophie/test_adapter.c'), '-o', str(exe),
            ], check=True)
            subprocess.run([str(exe)], check=True)


class SophieImageIdentityTests(unittest.TestCase):
    def run_gate(self, corruption=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('mainos_bus.bin', 'platform/runtime/runtime.elf', 'platform/layout.json'):
                path = root / 'out' / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'original')
            main = runpy.run_path(str(ROOT / 'tools/verify/verify_sophie_image.py'))['main']
            main.__globals__['ROOT'] = root
            calls = []

            def fake_run(command, **kwargs):
                calls.append(command)
                if command[1].endswith('verify_sophie_page.py'):
                    return
                options = dict(zip(command[4::2], command[5::2]))
                track = options['--track']
                case = options.get('--case', 'midi-mono')
                metal = options.get('--metal', '0')
                fine = options.get('--fine')
                suffix = f'-fine{fine}' if fine else ''
                receipt = root / f'out/sophie-port/t{track}-{case}-metal{metal}{suffix}/receipt.json'
                receipt.parent.mkdir(parents=True, exist_ok=True)
                image_hash = hashlib.sha256(b'original').hexdigest()
                receipt.write_text(json.dumps({'image_sha256': 'wrong' if corruption == 'receipt' else image_hash}))
                if corruption in ('mainos_bus.bin', 'platform/runtime/runtime.elf'):
                    (root / 'out' / corruption).write_bytes(b'concurrent rebuild')

            with patch.dict('os.environ', {'OT_PROJECT': str(root / 'fixture')}), \
                    patch('subprocess.run', side_effect=fake_run):
                main()
            self.assertEqual(len(calls), 6)
            self.assertTrue((root / 'out/sophie-frozen/verified-inputs.json').exists())

    def test_all_cases_share_frozen_inputs(self):
        self.run_gate()

    def test_changed_image_or_runtime_fails(self):
        for name in ('mainos_bus.bin', 'platform/runtime/runtime.elf'):
            with self.subTest(name=name), self.assertRaisesRegex(AssertionError, 'inputs changed'):
                self.run_gate(name)

    def test_wrong_case_image_fails(self):
        with self.assertRaisesRegex(AssertionError, 'different image'):
            self.run_gate('receipt')


if __name__ == '__main__':
    unittest.main()
