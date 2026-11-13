"""Timestamp recovery must not depend on original file/row ordering."""
import itertools
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'ncm'))
import prep

class TimeRecoveryTests(unittest.TestCase):
    def test_ambiguous_hours_and_shortest_wait_are_order_independent(self):
        raw=pd.DataFrame(dict(src=[1,2,99],sport=[1,2,99],dst=[3,3,3],dport=[80,80,80],proto=[6,6,6],ts=['15:01.0','16:02.5','00:00.0']))
        candidates=pd.DataFrame(dict(src=[1,1,2,2],sport=[1,1,2,2],dst=[3]*4,dport=[80]*4,proto=[6]*4,omin=[615,555,550,616]))
        for order in itertools.permutations(range(4)):
            with patch.object(prep,'load_orig',return_value=candidates.iloc[list(order)]):
                got,exact=prep.recover_time(raw.copy(),'friday')
            np.testing.assert_array_equal(got['src'],[1,2])
            np.testing.assert_allclose(got['t'],[555*60+1,616*60+2.5])
            self.assertEqual(exact,1.0)

if __name__=='__main__': unittest.main()
