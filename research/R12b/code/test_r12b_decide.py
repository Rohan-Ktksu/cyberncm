"""Regression checks for fail-closed R12b reporting. Run with Python stdlib only."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('r12b_decide.py')
RULES = [(2, 3, .995), (5, 6, .999), (12, 12, .999), (12, 12, .9999)]

def fixture(seed, sites, rule):
    counts = dict(att_windows=100, att_prevented=50, benign_combos_total=100,
                  benign_combos_own=1, benign_combos_nosite=99, benign_combos_blocked=0,
                  benign_windows_honest=100, benign_blocked_honest=0)
    return dict(seed=seed, K=sites, sites={str(i):dict(windows=100,day0_fit_windows=80,threshold=2.0) for i in range(sites)}, forged_blocks_per_hour=5.0, forged_total=10, rule=dict(zip(('k_of', 'n_of', 'quantile'), RULES[rule])),
                scenarios={s: {f'{e}_{p}': {'final': copy.deepcopy(counts)}
                               for e in ('Einf', 'E30') for p in ('none', 'share_all', 'two_agree')}
                           for s in ('honest', 'lying_site0')},
                attacker_site_pairs={'final': 2},
                time_to_block={'final': {p: [5, None] for p in ('none', 'share_all', 'two_agree')}})

class ReportTests(unittest.TestCase):
    def run_case(self, mode):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            references=root/'references';references.mkdir()
            report = root / 'report.md'
            report.write_text('OLD VERDICT')
            if mode != 'empty':
                for ds in ('cic2017', 'd2018', 'unraveled'):
                    for k in (2, 4):
                        for r in range(4):
                            for s in range(3):
                                data = fixture(s, k, r)
                                if r==0:
                                    baseline=copy.deepcopy(data)
                                    baseline.pop('rule')
                                    for scenario in baseline['scenarios'].values():
                                        for policy in scenario.values():
                                            for counts in policy.values():
                                                counts.pop('benign_combos_total');counts.pop('benign_combos_own')
                                    if mode=='baseline_mismatch':baseline['scenarios']['honest']['Einf_none']['final']['att_prevented']=49
                                    if mode=='baseline_ttb':baseline['time_to_block']['final']['none']=[6,None]
                                    if mode=='baseline_forgery':baseline['forged_total']=11
                                    if mode=='baseline_site':baseline['sites']['0']['windows']=101
                                    if mode=='unknown_counter':data['scenarios']['honest']['Einf_none']['final']['unexpected']=1
                                    if mode=='missing_counter':data['scenarios']['honest']['Einf_none']['final'].pop('att_prevented')
                                    (references/f'{ds}_k{k}_s{s}.json').write_text(json.dumps(baseline))
                                if mode == 'zero':
                                    data['scenarios']['honest']['Einf_none']['final']['att_windows'] = 0
                                if mode == 'metadata':
                                    data['seed'] = 8
                                if mode == 'population':
                                    data['time_to_block']['final']['none'] = []
                                (root / f'{ds}_k{k}_r{r}_s{s}.json').write_text(json.dumps(data))
                if mode == 'partial':
                    (root / 'unraveled_k4_r3_s2.json').unlink()
                if mode == 'unexpected':
                    (root / 'cic2017_k4_r3_s8.json').write_text('{}')
            proc = subprocess.run([sys.executable, str(SCRIPT), str(root), str(report), *([] if mode=='no_reference' else [str(references)])], capture_output=True, text=True)
            return proc.returncode, report.read_text()

    def test_complete(self):
        code, report = self.run_case('complete')
        self.assertEqual(code, 0)
        self.assertIn('exploratory', report)
        self.assertIn('### Verdict', report)
        self.assertIn('Threshold sensitivity',report)
        self.assertIn('| strict |',report)
        self.assertIn('| lenient |',report)

    def test_invalid_inputs_never_leave_a_verdict(self):
        for mode in ('empty', 'partial', 'unexpected', 'zero', 'metadata', 'population', 'baseline_mismatch', 'baseline_ttb', 'baseline_forgery', 'baseline_site', 'unknown_counter', 'missing_counter', 'no_reference'):
            with self.subTest(mode=mode):
                code, report = self.run_case(mode)
                self.assertNotEqual(code, 0)
                self.assertIn('INCOMPLETE', report)
                self.assertNotIn('OLD VERDICT', report)
                self.assertNotIn('### Verdict', report)

if __name__ == '__main__':
    unittest.main()
