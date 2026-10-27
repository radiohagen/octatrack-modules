"""The firmware loader must initialize every Euclid state variable."""
from pathlib import Path
import runpy
import shutil
import unittest

ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(all(shutil.which(tool) for tool in
                        ('m68k-elf-gcc', 'm68k-elf-as', 'm68k-elf-nm')),
                     'ColdFire toolchain required')
class EuclidSourceTests(unittest.TestCase):
    def test_loader_initializes_both_retention_variants(self):
        generator = runpy.run_path(str(ROOT/'modules/euclid-lfo/generate_control.py'))
        for sidecar, name in ((False, 'control.s'), (True, 'control-sidecar.s')):
            with self.subTest(sidecar=sidecar):
                self.assertEqual(generator['generate'](sidecar),
                                 (ROOT/'modules/euclid-lfo'/name).read_text())

    def test_original_bss_regression_is_rejected(self):
        generator = runpy.run_path(str(ROOT/'modules/euclid-lfo/generate_control.py'))
        generator['FLAGS'].remove('-fno-zero-initialized-in-bss')
        for sidecar in (False, True):
            with self.subTest(sidecar=sidecar):
                with self.assertRaisesRegex(RuntimeError, 'rate_writing'):
                    generator['generate'](sidecar)
