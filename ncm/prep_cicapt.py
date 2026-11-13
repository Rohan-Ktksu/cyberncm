"""CICAPT-IIoT 2024 network CSVs (one row per packet) -> data/windows.npz, same 5 s per-source windows and 32 features
as prep.py (reuses prep.windows). Usage: python prep_cicapt.py PHASE1.csv PHASE2.csv

Packets -> flow slices: bidirectional 5-tuple inside one 5 s window (a connection is cut at every window boundary, so
activity lands in the window where its packets occur; attack traffic here runs over long-lived connections). The first
packet of a slice sets its forward direction.
Days (fixed before any model ran): day 0 = all of phase 1 (27 Nov - 1 Dec 2023, no attack label; benign train and
calibration). Phase 2 is split by calendar date (UTC), one day each, in time order.
family = "APT:<tactic>" if any packet of the flow carries that tactic (the CSV's subLabel column), BENIGN otherwise.
Dropped: packets without an IPv4 source or destination (ARP, LLC).
Approximations: no TCP initial window in the CSV (iwin = 0); piat = flow duration / (packets - 1).
"""
import ipaddress, sys
import numpy as np, pandas as pd
from prep import FEATURES, windows

P1, P2 = sys.argv[1], sys.argv[2]
USE = ['ts', 'Source IP', 'Destination IP', 'Source Port', 'Destination Port', 'Protocol Type', 'Tot size',
       'fin_flag_number', 'syn_flag_number', 'rst_flag_number', 'psh_flag_number', 'ack_flag_number', 'label', 'subLabel']
FLAGS = ['fin', 'syn', 'rst', 'psh', 'ack']
TACTICS = ['BENIGN']
ipc = {}


def ip_int(s):
    for x in pd.unique(s):
        if x not in ipc:
            try: ipc[x] = int(ipaddress.IPv4Address(x))
            except (ValueError, TypeError): ipc[x] = -1
    return s.map(ipc).values.astype(np.int64)


def packets(path):
    cols = {k: [] for k in ['ts', 's', 'd', 'sp', 'dp', 'pr', 'size', 'lab'] + FLAGS}
    n = 0
    for ch in pd.read_csv(path, usecols=USE, chunksize=2_000_000, dtype={'Source IP': str, 'Destination IP': str, 'label': str, 'subLabel': str}):
        n += len(ch)
        s, d = ip_int(ch['Source IP']), ip_int(ch['Destination IP'])
        ok = (s >= 0) & (d >= 0)
        tac = np.where(ch['label'].values != '0', ch['subLabel'].fillna('unknown').values, 'BENIGN')
        for x in pd.unique(tac):
            if x not in TACTICS: TACTICS.append(x)
        num = lambda c, t: pd.to_numeric(ch[c], errors='coerce').fillna(0).values.astype(t)[ok]
        cols['ts'].append(ch['ts'].values.astype(np.float64)[ok]); cols['s'].append(s[ok]); cols['d'].append(d[ok])
        cols['sp'].append(num('Source Port', np.int64)); cols['dp'].append(num('Destination Port', np.int64))
        cols['pr'].append(num('Protocol Type', np.int64)); cols['size'].append(num('Tot size', np.int64))
        cols['lab'].append(np.array([TACTICS.index(x) for x in tac], np.int64)[ok])
        for f in FLAGS: cols[f].append(num(f + '_flag_number', np.int64))
    p = {k: np.concatenate(v) for k, v in cols.items()}
    print(f'{path}: {n} packets read, {len(p["ts"])} with IPv4 addresses', flush=True)
    return p


def flows(p):
    a, b = p['s'] * 65536 + p['sp'], p['d'] * 65536 + p['dp']
    lo, hi, is_lo = np.minimum(a, b), np.maximum(a, b), a <= b
    o = np.lexsort((p['ts'], p['pr'], hi, lo))
    lo, hi, is_lo = lo[o], hi[o], is_lo[o]
    q = {k: v[o] for k, v in p.items()}
    new = np.ones(len(o), bool)
    new[1:] = (lo[1:] != lo[:-1]) | (hi[1:] != hi[:-1]) | (q['pr'][1:] != q['pr'][:-1]) | (np.diff(np.floor(q['ts'] / 5)) != 0)
    st = np.flatnonzero(new); fid = np.cumsum(new) - 1; n = np.diff(np.append(st, len(o)))
    fwd = is_lo == is_lo[st][fid]
    end = np.append(st[1:], len(o)) - 1
    dur = q['ts'][end] - q['ts'][st]
    fpk = np.bincount(fid, fwd).astype(np.int64)
    fby = np.bincount(fid, q['size'] * fwd).astype(np.int64)
    tot = np.bincount(fid, q['size']).astype(np.int64)
    f = pd.DataFrame({'src': q['s'][st], 'sport': q['sp'][st], 'dst': q['d'][st], 'dport': q['dp'][st], 'proto': q['pr'][st],
                      't': q['ts'][st], 'dur': dur * 1e6, 'fpk': fpk, 'bpk': n - fpk, 'fby': fby, 'bby': tot - fby,
                      'flmax': np.maximum.reduceat(q['size'] * fwd, st), 'piat': np.where(n > 1, dur / np.maximum(n - 1, 1), 0) * 1e6,
                      'plmean': tot / n})
    for k in FLAGS: f[k] = np.bincount(fid, q[k]).astype(np.int64)
    f['iwin'] = 0
    f['lab'] = np.maximum.reduceat(q['lab'], st)
    return f


def ip(x): return str(ipaddress.IPv4Address(int(x)))


f1, f2 = flows(packets(P1)), flows(packets(P2))
assert (f1.lab == 0).all(), 'attack label inside phase 1'
date = pd.to_datetime(f2.t, unit='s').dt.strftime('%Y-%m-%d')
dates = sorted(set(date))
groups = [('train (phase 1)', f1)] + [(d, f2[(date == d).values]) for d in dates]
print(f'flows: phase 1 {len(f1)}, phase 2 {len(f2)} ({int((f2.lab > 0).sum())} attack flows); tactics {TACTICS[1:]}')
atk = f2[f2.lab > 0]
pairs = (atk.src.map(ip) + ' -> ' + atk.dst.map(ip)).value_counts()
print('attack flows by source -> destination:', pairs.to_dict())
for a in pd.unique(atk[['src', 'dst']].values.ravel()):
    print(f'  {ip(a)}: {int((f1.src == a).sum())} flows as source in phase 1 (benign training)')
out = {k: [] for k in ['X', 'day', 'src', 't', 'family']}
t0s = []
for di, (name, g) in enumerate(groups):
    g = g.copy()
    g['family'] = np.where(g.lab > 0, 'APT:' + np.array(TACTICS)[g.lab.values], 'BENIGN')
    g = g.drop(columns='lab')
    t0s.append(float(g.t.min())); g['t'] -= g.t.min()
    X, src, t, fam = windows(g)
    print(f'day {di} ({name}): {len(g)} flows, {len(X)} windows, {(fam != "BENIGN").sum()} attack windows', flush=True)
    for k, v in zip(out, [X, np.full(len(X), di), src, t, fam]): out[k].append(v)
X = np.concatenate(out['X']); assert np.isfinite(X).all()
fam = np.concatenate(out['family']); names = ['BENIGN'] + sorted(set(fam) - {'BENIGN'})
np.savez_compressed('data/windows.npz', X=X, day=np.concatenate(out['day']), src=np.concatenate(out['src']),
                    t=np.concatenate(out['t']), family=np.array([names.index(x) for x in fam]),
                    family_names=np.array(names), features=np.array(FEATURES), day_dates=np.array(['train'] + dates), day_t0=np.array(t0s))
print(pd.Series(fam).value_counts().to_string())
