"""Regression checks for key-aligned dataset comparison."""
from pathlib import Path
import tempfile
import unittest
import numpy as np
from compare_windows import compare

class ComparisonTests(unittest.TestCase):
    def test_alignment_and_changed_rows(self):
        with tempfile.TemporaryDirectory() as td:
            a, b = Path(td)/'a.npz', Path(td)/'b.npz'
            data = dict(X=np.array([[1.],[2.],[3.]]), day=np.array([0,1,1]), src=np.array([1,1,2]),
                        t=np.array([0.,5.,5.]), family=np.array([0,1,0]),
                        features=np.array(['x']), family_names=np.array(['BENIGN','Attack']))
            np.savez(a, **data)
            reverse = {k: v[[2,1,0]] if k in ('X','day','src','t','family') else v for k,v in data.items()}
            np.savez(b, **reverse)
            result = compare([a,b])['comparisons'][0]
            self.assertEqual(result['changed_feature_rows_exact'],0)
            self.assertEqual(result['common_keys'],3)
            reverse['X'] = reverse['X'].copy()
            reverse['X'][0,0] = 9
            np.savez(b, **reverse)
            self.assertEqual(compare([a,b])['comparisons'][0]['changed_feature_rows_exact'],1)

if __name__ == '__main__':
    unittest.main()
