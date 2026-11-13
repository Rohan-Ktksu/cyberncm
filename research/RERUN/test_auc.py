"""Weighted AUC must not change when tied rows are permuted."""
from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ncm'))
from scoreboard import wauc

class AucTests(unittest.TestCase):
    def test_ties_and_permutations(self):
        for order in ([0,1,2,3], [3,2,1,0], [1,3,0,2]):
            i = np.array(order)
            self.assertAlmostEqual(wauc(np.ones(4)[i], np.array([True,False,True,False])[i], np.array([1,3,2,4])[i]), .5)

    def test_known_weighted_result(self):
        # Positive weight 2 at score .5, negative weights 1 at .2 and 3 at .5.
        self.assertAlmostEqual(wauc(np.array([.5,.2,.5]), np.array([True,False,False]), np.array([2,1,3])), .625)

    def test_missing_weighted_class(self):
        self.assertTrue(np.isnan(wauc(np.array([0.,1.]), np.array([True,False]), np.array([1,0]))))

if __name__ == '__main__':
    unittest.main()
