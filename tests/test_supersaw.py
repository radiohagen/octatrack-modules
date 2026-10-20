"""Firmware-free Supersaw arithmetic and marker regression checks."""
from pathlib import Path
import shutil
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

if __name__ == '__main__': unittest.main()
