"""Unraveled (DAPT2021) labelled NFStream flows -> data/windows.npz, same 5 s per-source windows and 32 features
as prep.py (reuses prep.windows).

Input: /content/data/unraveled/flows/**/*.csv, the 173 files under processed/network-flows/ of the public bucket
https://dapt2021.s3.amazonaws.com (3.47 GB, no registration).
Days (fixed before any model ran): day 0 = 2021-05-28 .. 2021-06-02, the only multi-day stretch with no malicious
label (benign train + calibration). Every other calendar date (UTC) is its own day, in time order.
family = "<Signature>:<Stage>" for malicious flows (e.g. "APT:Lateral Movement"), BENIGN otherwise.
Dropped: rows with a wrong field count (unquoted commas), rows whose Stage is not a known label, non-IPv4 rows,
exact duplicates of (5-tuple, start ms) - the gateway capture repeats flows seen on the subnets.
Approximations: NFStream has no TCP initial window (iwin = 0); flmax = src2dst_max_ps; piat = mean packet IAT.
"""
import glob, ipaddress
import numpy as np, pandas as pd
from prep import FEATURES, windows

C = {'src_ip': 'src_ip', 'src_port': 'sport', 'dst_ip': 'dst_ip', 'dst_port': 'dport', 'protocol': 'proto',
     'ip_version': 'ipv', 'bidirectional_first_seen_ms': 'ms', 'bidirectional_duration_ms': 'dur',
     'src2dst_packets': 'fpk', 'dst2src_packets': 'bpk', 'src2dst_bytes': 'fby', 'dst2src_bytes': 'bby',
     'src2dst_max_ps': 'flmax', 'bidirectional_mean_piat_ms': 'piat', 'bidirectional_mean_ps': 'plmean',
     'bidirectional_fin_packets': 'fin', 'bidirectional_syn_packets': 'syn', 'bidirectional_rst_packets': 'rst',
     'bidirectional_psh_packets': 'psh', 'bidirectional_ack_packets': 'ack', 'Stage': 'Stage', 'Signature': 'Signature'}
STAGES = ['Reconnaissance', 'Establish Foothold', 'Lateral Movement', 'Data Exfiltration', 'Cover up']
F = sorted(glob.glob('/content/data/unraveled/flows/**/*.csv', recursive=True))
d = pd.concat([pd.read_csv(f, usecols=list(C), dtype=str, on_bad_lines='skip') for f in F], ignore_index=True).rename(columns=C)
n0 = len(d)
d = d[d.Stage.isin(STAGES + ['Benign', 'Normal']) & (d.ipv == '4')]
num = [c for c in C.values() if c not in ('src_ip', 'dst_ip', 'Stage', 'Signature', 'ipv')]
d[num] = d[num].apply(pd.to_numeric, errors='coerce')
d = d.dropna(subset=num)
cache = {}
def ip_int(s):
    for x in pd.unique(s):
        if x not in cache:
            try: cache[x] = int(ipaddress.IPv4Address(x))
            except ValueError: cache[x] = -1
    return s.map(cache).values
d['src'], d['dst'] = ip_int(d.src_ip), ip_int(d.dst_ip)
d = d[(d.src >= 0) & (d.dst >= 0)].drop_duplicates(['src', 'sport', 'dst', 'dport', 'proto', 'ms'])
mal = d.Stage.isin(STAGES)
d['family'] = np.where(mal, d.Signature.fillna('NA') + ':' + d.Stage, 'BENIGN')
print(f'{n0} rows read, {len(d)} kept, {int(mal.sum())} malicious')
ts = pd.to_datetime(d.ms, unit='ms')
date = ts.dt.strftime('%Y-%m-%d')
train = (date >= '2021-05-28') & (date <= '2021-06-02')
assert (d.family[train] == 'BENIGN').all(), 'malicious flow inside the benign training span'
others = sorted(set(date[~train]))
day = np.where(train, 0, date.map({x: i + 1 for i, x in enumerate(others)}).fillna(0)).astype(int)
d['t'] = d.ms / 1e3
d['dur'] *= 1e3; d['piat'] *= 1e3  # ms -> microseconds, as in the CIC flows
d['iwin'] = 0
keep = ['src', 'sport', 'dst', 'dport', 'proto', 't', 'dur', 'fpk', 'bpk', 'fby', 'bby', 'flmax', 'piat', 'plmean',
        'fin', 'syn', 'rst', 'psh', 'ack', 'iwin', 'family']
for c in ['sport', 'dport', 'proto', 'fpk', 'bpk', 'fby', 'bby', 'fin', 'syn', 'rst', 'psh', 'ack', 'iwin']:
    d[c] = d[c].astype(np.int64)
out = {k: [] for k in ['X', 'day', 'src', 't', 'family']}
t0s = []
for di in range(len(others) + 1):
    g = d.loc[day == di, keep].copy()
    t0s.append(float(g['t'].min()))  # epoch seconds of the day's first flow; t below is relative to it
    g['t'] -= g['t'].min()
    X, src, t, fam = windows(g)
    print(f"day {di} ({'train 05-28..06-02' if di == 0 else others[di - 1]}): {len(g)} flows, {len(X)} windows, "
          f"{(fam != 'BENIGN').sum()} attack windows", flush=True)
    for k, v in zip(out, [X, np.full(len(X), di), src, t, fam]): out[k].append(v)
X = np.concatenate(out['X']); assert np.isfinite(X).all()
fam = np.concatenate(out['family']); names = ['BENIGN'] + sorted(set(fam) - {'BENIGN'})
np.savez_compressed('data/windows.npz', X=X, day=np.concatenate(out['day']), src=np.concatenate(out['src']),
                    t=np.concatenate(out['t']), family=np.array([names.index(x) for x in fam]),
                    family_names=np.array(names), features=np.array(FEATURES), day_dates=np.array(['train'] + others), day_t0=np.array(t0s))
print(pd.Series(fam).value_counts().to_string())
