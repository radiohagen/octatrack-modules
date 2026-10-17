"""Keep Harmony one implementation, with one complete assembly generator."""
import ast
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'modules/midi-harmony'


class HarmonySource(unittest.TestCase):
    def test_removed_retention_setting_is_retired(self):
        lock = json.loads((MODULE / 'brain.lock').read_text())
        self.assertEqual(lock['settings'], {})
        self.assertIn(1, lock['retired']['settings'])
        self.assertEqual(lock['store']['id'], 'mattias.midi-harmony')

    def test_manifest_has_one_storage_and_ui_implementation(self):
        tree = ast.parse((MODULE / 'manifest.py').read_text())
        call = next(node.value for node in tree.body
                    if isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'MODULE' for t in node.targets))
        fields = {kw.arg: kw.value for kw in call.keywords}
        self.assertNotIn('variant', fields)
        self.assertNotIn('settings', fields)
        self.assertEqual(set(ast.literal_eval(fields['requires'])),
                         {'MIDI PART STATE', 'MIDI SRAM', 'STORE'})
        for node in ast.walk(fields['linked']):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'Linked':
                source = ast.literal_eval(node.args[1])
                self.assertNotIn('/degrees/', source)
                self.assertTrue((ROOT / source).is_file(), source)

    def test_generator_covers_every_c_unit(self):
        tree = ast.parse((MODULE / 'generate.py').read_text())
        units = next(ast.literal_eval(node.value) for node in tree.body
                     if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'UNITS' for t in node.targets))
        self.assertEqual(set(units), {p.stem for p in MODULE.glob('*.c')})
        self.assertEqual(len(units), len(set(units)))

    def test_no_alternate_runtime_or_migration_readers(self):
        for path in MODULE.iterdir():
            if path.suffix not in ('.c', '.h', '.s', '.py'):
                continue
            source = path.read_text()
            for obsolete in ('HAVE_ACCUM', 'HD_TRACK_SRAM', 'ha_enabled_c',
                             'hd_legacy_hash_c', '.rd_legacy'):
                self.assertNotIn(obsolete, source, str(path))


if __name__ == '__main__':
    unittest.main()
