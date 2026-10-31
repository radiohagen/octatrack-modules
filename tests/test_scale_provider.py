"""Scale reader selection and composition contracts, without firmware tooling."""
import ast
from pathlib import Path
import runpy
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BINDING = runpy.run_path(str(ROOT / 'integration/scale_provider.py'))
PROVIDER = BINDING['scale_provider']
INCLUDE = BINDING['scale_inc']
LINKS = BINDING['scale_links']
# Musical identities are deliberately independent of the binding's constant.
SEVEN_MODES = frozenset((0xab5, 0x6ad, 0x5ab, 0xad5, 0x6b5, 0x5ad, 0x56b))


def adapter(key='OTHER SCALE', **changes):
    result = dict(key=key, reader='other_scale_read',
                  source=ROOT / 'integration/scale_key.s', owns_key_ui=True,
                  masks=SEVEN_MODES, include='.set OTHER_SCALE,1\n')
    result.update(changes)
    return result


def linked(label, source, **options):
    return SimpleNamespace(label=label, source=source, **options)


def module_selector(owner):
    directory = ROOT / 'modules' / owner.lower().replace(' ', '-')
    path = directory / 'manifest.py'
    tree = ast.parse(path.read_text())
    selector = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == 'select')
    scope = dict(ROOT=directory, _scale=BINDING, Linked=linked,
                 Detour=lambda *args, **options: SimpleNamespace(address=args[0]),
                 MODULE=SimpleNamespace(linked=(), detours=()))
    exec(compile(ast.Module(body=[selector], type_ignores=[]), str(path), 'exec'), scope)
    return scope['select']


class ScaleProviderBinding(unittest.TestCase):
    def test_stock_is_the_default_for_either_consumer(self):
        for modules in ({}, {'MIDI FOLLOW'}, {'MIDI HARMONY'},
                        {'MIDI FOLLOW', 'MIDI HARMONY', 'MIDI LOOPBACK'}):
            with self.subTest(modules=modules):
                provider = PROVIDER(modules)
                self.assertIsNone(provider['key'])
                self.assertEqual(provider['masks'], {0xab5, 0x5ad})
                self.assertFalse(provider['owns_key_ui'])
                self.assertIn('.set SCALE_OWNS_KEY_UI,0\n', INCLUDE(modules))

    def test_legacy_midi_scales_binds_all_seven_modes(self):
        modules = {'MIDI FOLLOW': object(), 'MIDI HARMONY': object(),
                   'MIDI SCALES': object()}
        provider = PROVIDER(modules)
        self.assertEqual(provider['key'], 'MIDI SCALES')
        self.assertEqual(provider['masks'], SEVEN_MODES)
        self.assertTrue(provider['owns_key_ui'])
        self.assertIn('.set SCALE_KEY_EXTENDED,1\n', provider['include'])

    def test_an_independent_reader_is_actually_bound(self):
        other = adapter(reader='different_local_scale_reader')
        with patch.dict(PROVIDER.__globals__, PROVIDERS=(other,)):
            output = INCLUDE({'MIDI FOLLOW', 'MIDI HARMONY', 'OTHER SCALE'})
            self.assertIn('.macro scale_read\n'
                          '    jsr different_local_scale_reader\n.endm\n', output)
            self.assertNotIn('msp_key_read', output)
            self.assertNotIn('ms_decode', output)
            self.assertEqual(output.count('.macro '), 3)
            for name in ('quant', 'legacy'):
                self.assertIn(f'.macro scale_{name}\n'
                              f'    jsr msp_{name}\n.endm\n', output)

    def test_invalid_adapter_is_rejected_even_when_not_selected(self):
        invalid = (adapter(key=''), adapter(reader='bad-name'),
                   adapter(reader='reader\njsr unexpected'),
                   adapter(masks=frozenset()), adapter(masks={0}),
                   adapter(masks={-1}), adapter(masks={0x1000}),
                   adapter(masks={'major'}), adapter(masks={True}))
        for record in invalid:
            with self.subTest(record=record):
                with patch.dict(PROVIDER.__globals__, PROVIDERS=(record,)):
                    with self.assertRaisesRegex(ValueError, 'invalid MIDI scale adapter'):
                        PROVIDER({'MIDI FOLLOW'})

    def test_duplicate_registration_is_not_a_selection_tiebreak(self):
        with patch.dict(PROVIDER.__globals__, PROVIDERS=(adapter(), adapter())):
            with self.assertRaisesRegex(ValueError, 'invalid MIDI scale adapter'):
                PROVIDER({'MIDI FOLLOW'})

    def test_two_selected_adapters_are_rejected(self):
        providers = (adapter('FIRST'), adapter('SECOND', reader='second_read'))
        with patch.dict(PROVIDER.__globals__, PROVIDERS=providers):
            self.assertEqual(PROVIDER({'MIDI FOLLOW', 'FIRST'})['key'], 'FIRST')
            self.assertEqual(PROVIDER({'MIDI FOLLOW', 'SECOND'})['key'], 'SECOND')
            with self.assertRaisesRegex(ValueError, 'only one selected adapter'):
                PROVIDER({'MIDI FOLLOW', 'FIRST', 'SECOND'})

    def test_unadapted_scales_is_never_implicitly_accepted(self):
        for modules in ({'MIDI FOLLOW', 'SCALES'}, {'MIDI HARMONY', 'SCALES'},
                        {'MIDI FOLLOW', 'MIDI HARMONY', 'SCALES'},
                        {'MIDI FOLLOW', 'MIDI SCALES', 'SCALES'}):
            with self.subTest(modules=modules):
                for action in (PROVIDER, INCLUDE,
                               lambda keys: LINKS(keys, 'MIDI FOLLOW')):
                    with self.assertRaisesRegex(ValueError, 'qualified MIDI scale adapter'):
                        action(modules)

    def test_scales_name_requires_an_explicit_qualified_adapter(self):
        provider = adapter('SCALES', reader='qualified_scales_read')
        with patch.dict(PROVIDER.__globals__, PROVIDERS=(provider,)):
            output = INCLUDE({'MIDI FOLLOW', 'MIDI HARMONY', 'SCALES'})
            self.assertIn('jsr qualified_scales_read', output)

    def test_harmony_accepts_each_exact_existing_mode(self):
        for mask in SEVEN_MODES:
            with self.subTest(mask=hex(mask)):
                provider = adapter(masks={mask})
                with patch.dict(PROVIDER.__globals__, PROVIDERS=(provider,)):
                    self.assertIs(PROVIDER({'MIDI HARMONY', 'OTHER SCALE'}), provider)
        provider = adapter()
        with patch.dict(PROVIDER.__globals__, PROVIDERS=(provider,)):
            self.assertIs(PROVIDER({'MIDI HARMONY', 'OTHER SCALE'}), provider)

    def test_harmony_rejects_other_scales_including_seven_note_scales(self):
        # Harmonic and melodic minor each have seven notes but cannot be
        # represented by Harmony's saved diatonic mode identity.
        for mask in (0x9ad, 0xaad, 0x295, 0x6db, 0xfff):
            for masks in ({mask}, SEVEN_MODES | {mask}):
                with self.subTest(mask=hex(mask), mixed=len(masks) > 1):
                    provider = adapter(masks=masks)
                    with patch.dict(PROVIDER.__globals__, PROVIDERS=(provider,)):
                        self.assertIs(PROVIDER({'MIDI FOLLOW', 'OTHER SCALE'}), provider)
                        with self.assertRaisesRegex(ValueError, 'seven existing diatonic'):
                            PROVIDER({'MIDI HARMONY', 'OTHER SCALE'})

    def test_reader_and_math_are_linked_once_for_both_consumers(self):
        schema = SimpleNamespace(Linked=linked)
        with patch.dict(sys.modules, {'remix': ModuleType('remix'),
                                      'remix.schema': schema}):
            for extra in (set(), {'MIDI SCALES'}):
                for consumers in ({'MIDI FOLLOW'}, {'MIDI HARMONY'},
                                  {'MIDI FOLLOW', 'MIDI HARMONY'}):
                    modules = extra | consumers
                    with self.subTest(modules=modules):
                        units = tuple(unit for owner in sorted(consumers)
                                      for unit in LINKS(modules, owner))
                        self.assertEqual([unit.label for unit in units],
                                         ['midiscaleprovider', 'midiscalemath'])
                        self.assertTrue(all(unit.dram for unit in units))
                        self.assertEqual(Path(units[0].source),
                                         ROOT / 'integration/scale_key.s')
                        expected = int(bool(extra))
                        self.assertEqual(units[0].include(modules),
                                         f'.set SCALE_KEY_EXTENDED,{expected}\n')
                        self.assertEqual(Path(units[1].source),
                                         ROOT / 'integration/scale_math.s')

    def test_independent_reader_source_and_include_are_selected(self):
        other = adapter(source=ROOT / 'integration/other_reader.s')
        schema = SimpleNamespace(Linked=linked)
        with patch.dict(PROVIDER.__globals__, PROVIDERS=(other,)):
            with patch.dict(sys.modules, {'remix': ModuleType('remix'),
                                          'remix.schema': schema}):
                modules = {'MIDI FOLLOW', 'OTHER SCALE'}
                reader, _math = LINKS(modules, 'MIDI FOLLOW')
                self.assertEqual(Path(reader.source), other['source'])
                self.assertEqual(reader.include(modules), '.set OTHER_SCALE,1\n')

    def test_actual_module_selectors_link_the_service_once(self):
        selectors = {owner: module_selector(owner)
                     for owner in ('MIDI FOLLOW', 'MIDI HARMONY')}
        schema = SimpleNamespace(Linked=linked)
        with patch.dict(sys.modules, {'remix': ModuleType('remix'),
                                      'remix.schema': schema}):
            for consumers in ({'MIDI FOLLOW'}, {'MIDI HARMONY'},
                              {'MIDI FOLLOW', 'MIDI HARMONY'}):
                for extra in (set(), {'MIDI SCALES'}):
                    modules = consumers | extra
                    with self.subTest(modules=modules):
                        labels = [unit.label for owner in consumers
                                  for unit in selectors[owner](modules)['linked']]
                        self.assertEqual(labels.count('midiscaleprovider'), 1)
                        self.assertEqual(labels.count('midiscalemath'), 1)
                        self.assertEqual(labels.count('harmonypitchresponse'),
                                         int(len(consumers) == 2))
                with self.assertRaisesRegex(ValueError, 'qualified MIDI scale adapter'):
                    for owner in consumers:
                        selectors[owner](consumers | {'SCALES'})

    def test_follow_respects_the_selected_adapters_ui_ownership(self):
        select = module_selector('MIDI FOLLOW')
        schema = SimpleNamespace(Linked=linked)
        with patch.dict(sys.modules, {'remix': ModuleType('remix'),
                                      'remix.schema': schema}):
            native = select({'MIDI FOLLOW'})
            self.assertEqual({detour.address for detour in native['detours']},
                             {0x4003b79c, 0x4007a3e2})
            provider = adapter()
            with patch.dict(PROVIDER.__globals__, PROVIDERS=(provider,)):
                self.assertNotIn('detours', select({'MIDI FOLLOW', 'OTHER SCALE'}))


if __name__ == '__main__':
    unittest.main()
