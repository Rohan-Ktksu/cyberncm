"""Tests for the synthetic sandbox data. The fast tests need no model and no real data.
The full build (train, evaluate, export; about 2 minutes) runs only with CYBERNCM_TEST_SANDBOX_BUILD=1."""
import ipaddress
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "sandbox"))
sys.path.insert(0, str(HERE))
import make_sandbox  # noqa: E402

DOC_NETS = [ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]


class SandboxDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.z = make_sandbox.generate()

    def test_format_matches_the_real_windows_file(self):
        z = self.z
        self.assertEqual(set(z), {"X", "day", "src", "t", "family", "family_names", "features"})
        self.assertEqual(z["X"].shape[1], 32)
        self.assertEqual(z["X"].dtype, np.float32)
        self.assertTrue(np.isfinite(z["X"]).all())
        self.assertEqual(len(set(map(len, (z["X"], z["day"], z["src"], z["t"], z["family"])))), 1)
        self.assertEqual(list(z["family_names"]), make_sandbox.FAMILIES)
        self.assertEqual(len(z["features"]), 32)

    def test_only_documentation_addresses_are_used(self):
        for s in np.unique(self.z["src"]):
            ip = ipaddress.ip_address(int(s))
            self.assertTrue(any(ip in n for n in DOC_NETS), f"{ip} is not a documentation address")
        self.assertIn(ipaddress.ip_address(make_sandbox.SUBJECT), [ipaddress.ip_address(int(s)) for s in np.unique(self.z["src"])])

    def test_day_zero_is_normal_only_and_each_split_has_every_family(self):
        z = self.z
        self.assertTrue((z["family"][z["day"] == 0] == 0).all())
        for split in ((1, 2), (3, 4)):
            m = np.isin(z["day"], split)
            for f in range(1, len(make_sandbox.FAMILIES)):
                self.assertGreaterEqual(int((z["family"][m] == f).sum()), 10, (split, f))

    def test_replay_window_is_covered_and_contains_the_mapped_attacker(self):
        z = self.z
        m = z["day"] == 4
        self.assertEqual(float(z["t"][m].min()), 0.0)            # the demo replays offsets from the first window of the day
        lo, hi = 25000.0, 25000.0 + 1260.0                        # config.REPLAY_START, REPLAY_DURATION
        in_window = m & (z["t"] >= lo) & (z["t"] <= hi)
        subject = int(ipaddress.ip_address(make_sandbox.SUBJECT))
        self.assertTrue(((z["src"] == subject) & in_window & (z["family"] == 4)).sum() >= 30)
        self.assertGreaterEqual(len(np.unique(z["src"][in_window])), 6)   # a mix of sources, not just the attacker

    def test_deterministic(self):
        again = make_sandbox.generate()
        for k in ("X", "day", "src", "t", "family"):
            np.testing.assert_array_equal(self.z[k], again[k])

    def test_sorted_by_day_source_time(self):
        z = self.z
        order = np.lexsort((z["t"], z["src"], z["day"]))
        np.testing.assert_array_equal(order, np.arange(len(order)))


@unittest.skipUnless(os.environ.get("CYBERNCM_TEST_SANDBOX_BUILD") == "1", "set CYBERNCM_TEST_SANDBOX_BUILD=1 to run the 2-minute build")
class SandboxBuildTests(unittest.TestCase):
    def test_full_build_produces_artifacts_the_demo_accepts(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            ck, onnx, win = make_sandbox.build(Path(td) / "b")
            self.assertTrue(ck.is_file() and onnx.is_file() and win.is_file())
            from bootstrap import ensure_setup
            info = ensure_setup(runtime_dir=Path(td) / "rt", checkpoint_path=ck, windows_path=win)
            self.assertEqual(info["model"]["format"], "onnx-fp32")


if __name__ == "__main__":
    unittest.main()
