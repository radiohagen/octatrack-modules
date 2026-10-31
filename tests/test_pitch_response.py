"""Source-level binding and ownership boundaries; runtime ABI is image-tested."""
import ast
from pathlib import Path
import runpy
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BINDING = runpy.run_path(str(ROOT / 'integration/pitch_response.py'))
PITCH_INC = BINDING['pitch_inc']


class PitchResponseBinding(unittest.TestCase):
    def test_absent_provider_emits_nothing(self):
        for selected in ({}, {'MIDI FOLLOW': object()},
                         frozenset({'MIDI FOLLOW', 'MIDI SCALES'})):
            with self.subTest(selected=selected):
                self.assertEqual(PITCH_INC(selected), '')

    def test_selected_provider_binds_six_direct_requests(self):
        output = PITCH_INC({'MIDI FOLLOW': object(), 'MIDI HARMONY': object()})
        self.assertTrue(output.startswith('.set HAVE_PITCH_RESPONSE,1\n'))
        self.assertEqual(output.count('.macro '), 6)
        for callback in ('capture', 'prepare', 'owned', 'quant', 'target', 'shift'):
            self.assertIn(f'.macro pitch_{callback}\n'
                          f'    jsr mh_pitch_{callback}\n.endm\n', output)

    def test_binding_has_no_provider_specific_dispatch_logic(self):
        with patch.dict(PITCH_INC.__globals__, PROVIDERS=(('OTHER', 'other_pitch'),)):
            output = PITCH_INC({'OTHER'})
            self.assertIn('jsr other_pitch_shift', output)
            self.assertNotIn('mh_', output)
            self.assertEqual(PITCH_INC({'MIDI HARMONY'}), '')

    def test_invalid_registrations_fail_even_when_absent(self):
        for providers in ((('', 'p'),), (('A', 'bad-name'),),
                          (('A', 'p'), ('A', 'q')), (('A', 'p'), ('B', 'p'))):
            with self.subTest(providers=providers):
                with patch.dict(PITCH_INC.__globals__, PROVIDERS=providers):
                    with self.assertRaisesRegex(ValueError, 'invalid MIDI pitch provider'):
                        PITCH_INC(set())

    def test_multiple_selected_owners_fail(self):
        with patch.dict(PITCH_INC.__globals__, PROVIDERS=(('A', 'p'), ('B', 'q'))):
            self.assertIn('jsr p_shift', PITCH_INC({'A'}))
            self.assertIn('jsr q_shift', PITCH_INC({'B'}))
            with self.assertRaisesRegex(ValueError, 'only one selected provider'):
                PITCH_INC({'A', 'B'})

    def test_harmony_adapter_is_selected_only_with_follow(self):
        # Execute the actual selector without importing Octabam's schema into
        # this source-only repository. The stand-ins retain its Linked inputs.
        module_root = ROOT / 'modules/midi-harmony'
        tree = ast.parse((module_root / 'manifest.py').read_text())
        selector = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == 'select')
        existing = object()
        scope = {'ROOT': module_root, 'MODULE': SimpleNamespace(linked=(existing,)),
                 '_scale': {'scale_links': lambda modules, owner: ()},
                 'Linked': lambda label, source, **kwargs:
                     SimpleNamespace(label=label, source=source, **kwargs)}
        exec(compile(ast.Module(body=[selector], type_ignores=[]),
                     str(module_root / 'manifest.py'), 'exec'), scope)
        self.assertEqual(scope['select'](frozenset({'MIDI HARMONY'})), {'linked': (existing,)})
        linked = scope['select'](frozenset({'MIDI HARMONY', 'MIDI FOLLOW'}))['linked']
        self.assertEqual(len(linked), 2)
        self.assertIs(linked[0], existing)
        self.assertEqual(linked[1].label, 'harmonypitchresponse')
        self.assertEqual(Path(linked[1].source), module_root / 'pitch-response.s')
        self.assertTrue(linked[1].dram)

    def test_follow_has_no_harmony_binding_or_symbols(self):
        for name in ('manifest.py', 'midi_follow.s', 'response.s'):
            with self.subTest(name=name):
                source = (ROOT / 'modules/midi-follow' / name).read_text()
                self.assertNotRegex(source, r'\b(?:HAVE_HARMONY|mh_\w+|hd_\w+)\b|MIDI HARMONY')


if __name__ == '__main__':
    unittest.main()
