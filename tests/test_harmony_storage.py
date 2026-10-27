"""Native codec oracles; only the hardware SRAM address is redirected to RAM."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'modules/midi-harmony'


class HarmonyStorageTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'C compiler required')
    def test_storage_sanitized(self):
        with tempfile.TemporaryDirectory(prefix='harmony-storage-') as tmp:
            tmp = Path(tmp)
            source = (MODULE / 'track-retention.c').read_text()
            self.assertEqual(source.count('0x1001614eu'), 1)
            redirected = tmp / 'track-retention.c'
            redirected.write_text('extern unsigned char retained_test_memory[];\n' +
                                  source.replace('0x1001614eu', '(uintptr_t)retained_test_memory'))
            exe = tmp / 'storage-test'
            subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', '-I', str(MODULE),
                            str(ROOT / 'tests/harmony_storage.c'), str(MODULE / 'packed.c'),
                            str(MODULE / 'roots.c'), str(redirected), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    unittest.main()
