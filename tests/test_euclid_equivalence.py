"""Bit-exact CPU-optimization oracle against the last pre-optimization engine.

The reference is compiled separately from its immutable Git revision: it does
not share candidate helpers, lookup tables, headers, or runtime-state layout.
Only public parameters and observable engine history cross the test boundary.
"""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASELINE = '88c64670c5847edae3e6ddf4ad897e8864d6ee63'
MODULE = Path('modules/euclid-lfo')
FUNCTIONS = ('defaults', 'normalize', 'masks', 'edit', 'process', 'clock',
             'audio_clock', 'audio_clock_cached')


@unittest.skipUnless(shutil.which('clang'), 'Clang sanitizer toolchain required')
class EuclidEquivalenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='euclid-equivalence-')
        cls.addClassCleanup(cls.directory.cleanup)
        temporary = Path(cls.directory.name)
        reference = temporary/'reference'
        reference.mkdir()
        for name in ('engine.c', 'engine.h'):
            try:
                result = subprocess.run(
                    ['git', 'show', f'{BASELINE}:{MODULE/name}'], cwd=ROOT,
                    check=True, capture_output=True)
            except subprocess.CalledProcessError as error:
                raise RuntimeError(
                    f'Euclid equivalence requires immutable baseline {BASELINE} '
                    f'({MODULE/name}) in local Git history. Restore that history '
                    'when using a shallow clone; this test does not fetch it or '
                    'silently substitute current source.\n'+
                    error.stderr.decode(errors='replace')) from error
            (reference/name).write_bytes(result.stdout)
        compiler = ['clang', '-std=c11', '-O2', '-g', '-Wall', '-Wextra',
                    '-Werror', '-fsanitize=address,undefined',
                    '-fno-sanitize-recover=all', '-fno-omit-frame-pointer']
        renamed = [f'-Deul_{name}=baseline_eul_{name}' for name in FUNCTIONS]
        harness = ROOT/'tests/euclid_equivalence.c'
        objects = []
        for name, source, include, flags in (
                ('reference-engine', reference/'engine.c', reference, renamed),
                ('reference-probe', harness, reference,
                 renamed+['-DEUL_REFERENCE=1']),
                ('candidate-engine', ROOT/MODULE/'engine.c', ROOT/MODULE, []),
                ('candidate-probe', harness, ROOT/MODULE, [])):
            output = temporary/f'{name}.o'
            subprocess.run(compiler+['-I', str(include)]+flags+
                           ['-c', str(source), '-o', str(output)],
                           check=True, capture_output=True, text=True)
            objects.append(str(output))
        cls.executable = temporary/'equivalence'
        subprocess.run(compiler+objects+['-o', str(cls.executable)], check=True,
                       capture_output=True, text=True)

    def run_oracle(self, *args):
        environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=0',
                           UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        return subprocess.run([str(self.executable), *args], check=False,
                              capture_output=True, text=True, timeout=30,
                              env=environment)

    def test_bit_exact_parameters_history_outputs_and_clocks(self):
        result = self.run_oracle()
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('bit-exact Euclid equivalence passed', result.stdout)

    def test_oracle_rejects_changed_output(self):
        result = self.run_oracle('--negative-control')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('mismatch: output', result.stderr)
