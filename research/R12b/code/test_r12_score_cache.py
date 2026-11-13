import tempfile,unittest
from pathlib import Path
import numpy as np
from r12_score_cache import site_scores
class CacheTests(unittest.TestCase):
 def test_exact_reuse_and_key_separation(self):
  calls=[]
  def compute():calls.append(1);return np.array([.1,.2,.3]),np.array([.1,.2]),1
  with tempfile.TemporaryDirectory() as d:
   a=site_scores(d,{'seed':0},compute);b=site_scores(d,{'seed':0},compute)
   self.assertEqual(len(calls),1);self.assertFalse(a[3]);self.assertTrue(b[3]);np.testing.assert_array_equal(a[0],b[0]);np.testing.assert_array_equal(a[1],b[1])
   self.assertNotEqual(np.quantile(b[1],.995),np.quantile(b[1],.999))
   site_scores(d,{'seed':1},compute);self.assertEqual(len(calls),2)
 def test_nonfinite_never_cached(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):site_scores(d,{},lambda:(np.array([np.nan]),np.array([1.]),1))
   self.assertFalse(list(Path(d).glob('*.npz')))
 def test_corrupt_cache_fails_closed(self):
  with tempfile.TemporaryDirectory() as d:
   site_scores(d,{},lambda:(np.array([1.]),np.array([1.]),1))
   next(Path(d).glob('*.npz')).write_bytes(b'corrupt')
   with self.assertRaises(ValueError):site_scores(d,{},lambda:None)
if __name__=='__main__':unittest.main()
