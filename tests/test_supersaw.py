"""Firmware-free Supersaw arithmetic and marker regression checks."""
from pathlib import Path
import math
import shutil
import runpy
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]

class SupersawTests(unittest.TestCase):
    def test_harmonic_bank_continuity(self):
        banks=runpy.run_path(str(ROOT/'modules/supersaw/generate.py'))['saw_banks']()
        self.assertEqual(len(banks),113)
        # Independent Fourier values at uneven phase positions cover every
        # blend, including the two-partial to fundamental-only transition.
        for index,row in enumerate(banks):
            self.assertEqual(len(row),2048)
            power=(index+15)//16
            low=1 if power==0 else 1<<(power-1)
            high=1<<power
            weight=1 if power==0 else (index-(power-1)*16)/16
            for phase in range(0,2048,61):
                expected=-20000/math.pi*sum(
                    math.sin(2*math.pi*h*phase/2048)/h*(1 if h<=low else weight)
                    for h in range(1,high+1))
                self.assertLessEqual(abs(row[phase]-expected),1.001)
        # Each smaller spectral step must stay within 1/16 of the old
        # octave jump, plus one integer-rounding unit per sample.
        for power in range(1,8):
            lo,hi=(power-1)*16,power*16
            old_peak=max(abs(a-b) for a,b in zip(banks[hi],banks[lo]))
            for index in range(lo+1,hi+1):
                peak=max(abs(a-b) for a,b in zip(banks[index],banks[index-1]))
                self.assertLessEqual(peak,math.ceil(old_peak/16)+1)

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
