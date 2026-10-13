"""Regression checks for the repository guard, without firmware inputs."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.check import check_files, check_pin


class RepositoryChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, text=''):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_source_and_relative_link_pass(self):
        self.write('README.md', '[guide](docs/guide.md#section)')
        self.write('docs/guide.md', '# Section\n')
        self.write('scripts/example.py', 'x = 1\n')
        self.assertEqual(check_files(self.root, ['README.md', 'docs/guide.md',
                                                 'scripts/example.py']), [])

    def test_missing_link_and_invalid_python_fail(self):
        self.write('README.md', '[missing](missing.md)')
        self.write('broken.py', 'def\n')
        self.assertEqual(len(check_files(self.root, ['README.md', 'broken.py'])), 2)

    def test_forced_tracked_artifacts_fail(self):
        self.write('firmware.bin')
        self.write('artifacts/report.txt')
        self.assertEqual(len(check_files(self.root, ['firmware.bin',
                                                    'artifacts/report.txt'])), 2)

    def test_real_module_requires_manifest_and_readme(self):
        self.write('modules/new-feature/code.s', '; source\n')
        self.assertEqual(len(check_files(self.root, ['modules/new-feature/code.s'])), 2)

    def test_template_is_not_a_module(self):
        self.write('modules/_template/README.md', 'Inactive template\n')
        self.assertEqual(check_files(self.root, ['modules/_template/README.md']), [])

    def test_tracked_symlink_fails(self):
        self.write('source.py', 'x = 1\n')
        (self.root / 'link.py').symlink_to('source.py')
        self.assertTrue(check_files(self.root, ['link.py']))

    def test_pinned_submodule_can_be_uninitialized(self):
        name = 'modules/sophie/upstream'
        self.assertEqual(check_files(self.root, [name], frozenset({name})), [])
        self.assertTrue(check_files(self.root, [name]))

    def test_exact_pin_passes_and_moving_branch_fails(self):
        pin = {'repository': 'https://github.com/sambanks/octabam.git',
               'commit': 'a' * 40, 'status': 'reference-only',
               'recorded_on': '2026-10-13', 'note': 'Reference only.'}
        path = self.write('pin.json', json.dumps(pin))
        self.assertEqual(check_pin(path), [])
        pin['commit'] = 'main'
        path.write_text(json.dumps(pin))
        self.assertTrue(check_pin(path))

    def test_invalid_pin_data_fails(self):
        for value in ('[]', '{}', 'not json'):
            with self.subTest(value=value):
                self.assertTrue(check_pin(self.write('pin.json', value)))


if __name__ == '__main__':
    unittest.main()
