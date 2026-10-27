"""Firmware-free Supersaw arithmetic and marker regression checks."""
from pathlib import Path
import shutil
import runpy
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]

class SupersawTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'C compiler required')
    def test_engine_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp)/'engine-test'
            subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror',
                '-fsanitize=address,undefined',str(ROOT/'modules/supersaw/test_engine.c'),
                '-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)

    @unittest.skipUnless(shutil.which('m68k-elf-gcc'), 'ColdFire compiler required')
    def test_diagnostics_are_opt_in(self):
        flags=runpy.run_path(str(ROOT/'modules/supersaw/generate.py'))['FLAGS']
        with tempfile.TemporaryDirectory() as tmp:
            for enabled in (False,True):
                out=Path(tmp)/('diag.s' if enabled else 'production.s')
                subprocess.run(['m68k-elf-gcc',*flags,
                    *(['-DSS_DIAGNOSTICS'] if enabled else []),'-S',
                    str(ROOT/'modules/supersaw/adapter.c'),'-o',str(out)],check=True)
                text=out.read_text()
                self.assertEqual('ss_diag_events:' in text,enabled)
                self.assertEqual('ss_diag_tracks:' in text,enabled)
                self.assertNotIn('.bss',text)

if __name__ == '__main__': unittest.main()
