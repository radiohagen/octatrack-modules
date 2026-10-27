"""Performance comparisons must retain identical inputs and outputs."""
import copy
from pathlib import Path
import runpy
import unittest


PROFILE = runpy.run_path(str(Path(__file__).resolve().parents[1]/
                            'tools/verify/verify_euclid_lfo_cpu.py'))


class EuclidCpuProfileTests(unittest.TestCase):
    def setUp(self):
        self.baseline = {'cases': [dict(kind='waveform', pattern='silent', mode=0,
                                      midi=0, stage='forward', calls=512,
                                      input_hash=123, output_hash=456,
                                      instructions=1000, long_divisions=5, peak=10)]}
        self.candidate = copy.deepcopy(self.baseline)
        self.candidate['cases'][0].update(instructions=700, long_divisions=0, peak=8)

    def test_comparison_allows_cost_changes(self):
        result = PROFILE['summarize'](self.candidate, self.baseline)
        self.assertEqual(result[0]['instruction_change_percent'], -30)
        self.assertEqual(result[0]['baseline_long_divisions'], 5)

    def test_rejects_changed_inputs_even_with_identical_output(self):
        self.candidate['cases'][0]['input_hash'] += 1
        with self.assertRaisesRegex(AssertionError, 'inputs changed'):
            PROFILE['compare'](self.candidate, self.baseline)

    def test_rejects_changed_output_or_call_count(self):
        for field in ('output_hash', 'calls'):
            with self.subTest(field=field):
                candidate = copy.deepcopy(self.candidate)
                candidate['cases'][0][field] += 1
                with self.assertRaises(AssertionError):
                    PROFILE['compare'](candidate, self.baseline)

    def test_rejects_missing_input_hashes_and_scenarios(self):
        for mutation in ('old-format', 'missing', 'duplicate'):
            with self.subTest(mutation=mutation):
                baseline = copy.deepcopy(self.baseline)
                if mutation == 'old-format': del baseline['cases'][0]['input_hash']
                elif mutation == 'missing': baseline['cases'] = []
                else: baseline['cases'].append(copy.deepcopy(baseline['cases'][0]))
                with self.assertRaises(AssertionError):
                    PROFILE['compare'](self.candidate, baseline)
