"""R2: does the model warn before an attack's next stage begins?

Usage (in the run directory, next to ncm.py and data/windows.npz): python r2_lead.py CKPT OUT_PREFIX [MIN_WINDOWS]

windows.npz must come from prep_unraveled.py or prep_cicapt.py: family names are "<attacker>:<stage>" and day_t0 holds
each day's absolute start. Each dataset holds one multi-stage campaign: a case study (n = 1), not a statistic.
MIN_WINDOWS (default 10): stages with fewer windows are left out of Part A.

Sequences: benign train span (day 0) per source, as trained. Test: ONE continuous sequence per source across all test
days, ordered by absolute time, so model state and smoothing carry over between days (stages are days apart).

Part A  unsupervised scores, every stage unseen: AUC per stage against all benign test windows.
Part B  lead time per (attacker, source address, stage) onset, 1% threshold from benign calibration windows:
          alert_1h   was the source above threshold at any window in the hour before the stage's first window
          lead_24h_s seconds from the earliest alert in the 24 h before onset to the onset (blank = none)
          delay_s    seconds from onset to the first alert at or after it
          prior_atk  attack-labelled windows of that source in the 24 h before onset (alerts may be on those)
        Base rate: share of benign (source, hour) blocks with any alert - what "alert_1h" gives by chance.
Part C  supervised, trained on the past only: for each APT stage onset T, a stage head is fitted on benign windows and
        attack windows that occurred BEFORE T, then scored on the new stage. With state, without state, random forest.
Control: the same test sequences with window order shuffled inside each (source, hour) block. If order matters to the
        model, ordered should beat shuffled.
"""
import json, sys
import numpy as np, pandas as pd, torch, torch.nn.functional as F
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
from ncm import NCM, ewma, score

CKPT, OUT = sys.argv[1], sys.argv[2]
MIN_WINDOWS = int(sys.argv[3]) if len(sys.argv) > 3 else 10
torch.manual_seed(0); rng = np.random.default_rng(0); torch.set_num_threads(4)
z = np.load('data/windows.npz')
X, day, src, t, fam = z['X'], z['day'], z['src'], z['t'], z['family']
names = list(z['family_names'])
T = z['day_t0'][day] + t  # absolute epoch seconds of each window
UNRAVELED = ['Reconnaissance', 'Establish Foothold', 'Lateral Movement', 'Data Exfiltration', 'Cover up']
found = sorted({n.split(':')[1] for n in names if n != 'BENIGN'})
ST = ['Benign'] + (UNRAVELED if set(found) <= set(UNRAVELED) else found)  # Unraveled keeps its original class order
stage = np.array([0 if n == 'BENIGN' else ST.index(n.split(':')[1]) for n in names])[fam]
sig = np.array(['' if n == 'BENIGN' else n.split(':')[0] for n in names])[fam]
test = day > 0
ck = torch.load(CKPT)
model = NCM(h=ck['h'], arch=ck['arch']); model.load_state_dict(ck['state'], strict=False)
cal = (day == 0) & (t >= ck['cut'])
chrono = list(np.argsort(z['day_t0']))


def rolling(sc, clean=False):
    """Per-window 1% threshold recalibrated daily: the 99th percentile of ALL windows of the previous day (no labels,
    so yesterday's attacks raise it). The fixed calibration value is used when the previous day is the training span.
    clean=True uses only the benign-labelled windows of the previous day: not deployable (needs labels), it shows what
    recalibration would give if yesterday's attacks did not contaminate the threshold."""
    thr = np.full(len(sc), np.quantile(sc[cal], 0.99))
    for i, d in enumerate(chrono):
        if d != 0 and i > 0 and chrono[i - 1] != 0:
            m = (day == chrono[i - 1]) & ((stage == 0) | (not clean))
            thr[day == d] = np.quantile(sc[m], 0.99)
    return thr


def build(order_time):
    out = []
    for idx in (np.flatnonzero(~test), np.flatnonzero(test)):
        tt = T if idx[0] == np.flatnonzero(~test)[0] else order_time
        o = idx[np.lexsort((tt[idx], src[idx]))]
        out += np.split(o, np.flatnonzero(np.diff(src[o])) + 1)
    return out


Tsh = np.floor(T / 3600) * 3600 + rng.random(len(T)) * 3600  # shuffled position inside the same hour
ORD = {'ordered': (build(T), T), 'shuffled': (build(Tsh), Tsh)}
Zn = model.normalize(torch.from_numpy(X)).numpy()
SC, STATE = {}, {}
for o, (seqs, _) in ORD.items():
    comp, S = score(model, X, seqs)
    c = (comp - comp[cal].mean(0)) / comp[cal].std(0)
    STATE[o] = S
    SC[o] = {'NCM (all three signals)': ewma(c[:, 0] + c[:, 1] + 0.5 * (c[:, 2] + c[:, 3]), seqs),
             'token distance only': ewma(c[:, 0], seqs),
             'next-context surprise only': ewma(0.5 * (c[:, 2] + c[:, 3]), seqs)}
ben_test = test & (stage == 0)
attackers = np.unique(src[stage > 0])
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
res = {}

# ---------- Part A ----------
rows = {}
for f in range(1, len(names)):
    m = fam == f
    if m.sum() < MIN_WINDOWS: continue
    mm = ben_test | m
    rows[names[f]] = {'windows': int(m.sum())} | {f'{k} [{o}]': roc_auc_score(m[mm], SC[o][k][mm]) for o in ORD for k in SC[o]}
A = pd.DataFrame(rows).T
print(f'{CKPT}: {int(ben_test.sum())} benign and {int((test & (stage > 0)).sum())} attack test windows, {len(attackers)} attacker addresses\n')
print('PART A - unsupervised AUC per stage vs all benign test windows; [shuffled] = window order shuffled within the hour')
print(A.round(3).to_string(), '\n'); res['auc_per_stage'] = A.to_dict()

# ---------- Part B ----------
on = pd.DataFrame({'sig': sig, 'src': src, 'stage': stage, 'T': T})[stage > 0]
on = on.groupby(['sig', 'src', 'stage']).agg(onset=('T', 'min'), windows=('T', 'size')).reset_index().sort_values('onset')


def ip(x): return '.'.join(str((int(x) >> s) & 255) for s in (24, 16, 8, 0))


def lead_rows(sc, thr, time, onsets):
    out = []
    for r in onsets.itertuples():
        m = test & (src == r.src)
        tm, al, atk = time[m], sc[m] > (thr[m] if np.ndim(thr) else thr), stage[m] > 0
        first = time[m & (stage == r.stage) & (sig == r.sig)].min()
        d1, h1 = (tm >= first - 86400) & (tm < first), (tm >= first - 3600) & (tm < first)
        after = tm[(tm >= first) & al]
        out.append({'attacker': r.sig, 'source': ip(r.src), 'stage': ST[r.stage], 'onset': str(pd.to_datetime(r.onset, unit='s'))[:16],
                    'stage_windows': r.windows, 'windows_prev_24h': int(d1.sum()), 'prior_atk': int((d1 & atk).sum()),
                    'alert_1h': bool((h1 & al).any()), 'lead_24h_s': float(first - tm[d1 & al].min()) if (d1 & al).any() else np.nan,
                    'delay_s': float(after.min() - first) if len(after) else np.nan})
    return pd.DataFrame(out)


def base_rate(sc, thr, time):
    m = ben_test & ~np.isin(src, attackers)
    b = pd.DataFrame({'s': src[m], 'h': np.floor(time[m] / 3600), 'a': sc[m] > (thr[m] if np.ndim(thr) else thr)})
    return float(b.groupby(['s', 'h']).a.any().mean()), float(b.a.mean())


print('PART B - lead time per (attacker, source, stage) onset, 1% threshold: fixed from calibration, and recalibrated daily')
res['lead'] = {}
for o, (_, time) in ORD.items():
    for k in SC[o]:
        for mode, thr in (('fixed threshold', np.quantile(SC[o][k][cal], 0.99)), ('daily recalibration', rolling(SC[o][k])),
                          ('daily recalibration, benign-only (uses labels)', rolling(SC[o][k], True))):
            L = lead_rows(SC[o][k], thr, time, on)
            hr, wr = base_rate(SC[o][k], thr, time)
            print(f'\n{k} [{o}], {mode}:  benign false-alarm rate {wr:.3f} of windows, {hr:.3f} of (source, hour) blocks')
            print(L.to_string(index=False))
            res['lead'][f'{k} [{o}] {mode}'] = {'rows': L.to_dict('records'), 'benign_window_rate': wr, 'benign_source_hour_rate': hr}

# ---------- Part C ----------
def fit_head(feats, y, epochs=300):
    head = torch.nn.Sequential(torch.nn.Linear(feats.shape[1], 64), torch.nn.GELU(), torch.nn.Linear(64, len(ST)))
    w = torch.tensor([len(y) / (len(ST) * max((y == k).sum(), 1)) for k in range(len(ST))], dtype=torch.float32)
    xb, yb = torch.from_numpy(feats), torch.from_numpy(y)
    opt = torch.optim.AdamW(head.parameters(), 3e-3, weight_decay=1e-2)
    for _ in range(epochs):
        opt.zero_grad(); F.cross_entropy(head(xb), yb, weight=w).backward(); opt.step()
    return head.eval()


def hazard(head, feats):
    with torch.no_grad():
        return 1 - F.softmax(head(torch.from_numpy(feats)), -1)[:, 0].numpy()


print('\nPART C - supervised, trained only on windows BEFORE each APT stage onset; AUC on the new stage vs later benign windows')
apt = on[on.sig == 'APT'].groupby('stage').onset.min().sort_values()
block = (np.floor(T / 1800) % 2).astype(int)
seqs = ORD['ordered'][0]
surp = SC['ordered']['NCM (all three signals)']
rowsC, res['lead_supervised'] = {}, {}
for s, Ts in apt.items():
    past_atk = test & (stage > 0) & (T < Ts)
    past_ben = np.flatnonzero(ben_test & (T < Ts) & (block == 0))
    if past_atk.sum() < 20 or len(past_ben) < 1000:
        print(f'{ST[s]} (onset {pd.to_datetime(Ts, unit="s")}): skipped, only {int(past_atk.sum())} earlier attack windows'); continue
    past_ben = rng.choice(past_ben, min(len(past_ben), 200_000), replace=False)
    tr = np.concatenate([past_ben, np.flatnonzero(past_atk)])
    held = (stage == s) & (sig == 'APT')
    te_ben = np.flatnonzero(ben_test & (T >= Ts) & (block == 1))
    te = np.concatenate([rng.choice(te_ben, min(len(te_ben), 300_000), replace=False), np.flatnonzero(held)])
    row = {'onset': str(pd.to_datetime(Ts, unit='s'))[:16], 'train_attack_windows': int(past_atk.sum()), 'windows': int(held.sum())}
    cand = {}
    for o in ORD:
        feats = np.hstack([STATE[o], Zn]).astype(np.float32)
        cand[f'head with state [{o}]'] = ewma(hazard(fit_head(feats[tr], stage[tr]), feats), ORD[o][0])
    cand['head without state'] = ewma(hazard(fit_head(Zn[tr], stage[tr]), Zn), seqs)
    rf = RandomForestClassifier(n_estimators=200, n_jobs=4, class_weight='balanced', random_state=0)
    cand['RF single-window, smoothed'] = ewma(rf.fit(X[tr], stage[tr] > 0).predict_proba(X)[:, 1], seqs)
    cand['NCM surprise (unsupervised)'] = surp
    for k, v in cand.items():
        row[k] = roc_auc_score(held[te], v[te])
    rowsC[ST[s]] = row
    o_s = on[(on.sig == 'APT') & (on.stage == s)]
    for k in ('head with state [ordered]', 'head with state [shuffled]', 'head without state', 'RF single-window, smoothed'):
        time = Tsh if 'shuffled' in k else T
        for mode, clean in (('daily recalibration', False), ('daily recalibration, benign-only (uses labels)', True)):
            thr = rolling(cand[k], clean)
            L = lead_rows(cand[k], thr, time, o_s); hr, wr = base_rate(cand[k], thr, time)
            print(f'\n{ST[s]}: {k}, {mode}:  benign false-alarm rate {wr:.3f} of windows, {hr:.3f} of (source, hour) blocks')
            print(L.to_string(index=False))
            res['lead_supervised'][f'{ST[s]} | {k} | {mode}'] = {'rows': L.to_dict('records'), 'benign_window_rate': wr, 'benign_source_hour_rate': hr}
C = pd.DataFrame(rowsC).T
print('\nAUC on the new stage'); print(C.to_string()); res['supervised_auc'] = C.to_dict()
json.dump(res, open(OUT + '_results.json', 'w'), indent=1, default=float)
