"""Hand-checked example for metrics.py. Run: python test_metrics.py"""
import math
import metrics as M

# sources 1, 2 benign; 3 and 4 attack. Source 3 alerts on its second attack window; source 4 alerts only
# on a benign window before it attacks, so it must not count as detected.
src = [1, 1, 1, 1, 2, 2, 3, 3, 3, 4, 4]
t = [0, 5, 3600, 3605, 0, 5, 0, 5, 10, 0, 100]
atk = [0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 1]
alert = [1, 1, 0, 0, 0, 0, 1, 0, 1, 1, 0]

assert math.isclose(M.benign_window_rate(alert, src, t, atk), 2 / 6)           # 6 benign-source windows, 2 flagged
assert math.isclose(M.benign_source_hour_rate(alert, src, t, atk), 1 / 3)      # (1,h0) yes, (1,h1) no, (2,h0) no
assert math.isclose(M.false_alerts_per_host_day(alert, src, t, atk), 1 / 2)    # one episode over two host-days
assert M.detected_within(alert, src, t, atk) == {1: 0.5, 5: 0.5, 60: 0.5}
assert math.isclose(M.attack_windows_blocked(alert, atk), 1 / 3)
# a gap larger than gap_s starts a second episode
assert math.isclose(M.false_alerts_per_host_day([1, 1, 0], [1, 1, 2], [0, 600, 0], [0, 0, 0], gap_s=60), 2 / 2)
print("metrics checks passed")
