"""The agent's detector: learn the site's normal traffic, then score windows (shadow mode only).
Learning period: the base model's backbone is kept; normalisation, both vocabularies and the calibration are refitted on the site's own windows (research/R11, level 3).
Alert rule (as research/R12): at least 2 of a source's last 3 windows above the 99.5th percentile of the calibration windows.
History is truncated to the last 32 windows per source (the research code uses the whole day)."""
import os, sys
import numpy as np, torch
from sklearn.cluster import MiniBatchKMeans
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "ncm"))
from ncm import NCM, ewma, score, sequences   # noqa: E402

HISTORY, EWMA_A, PCT = 32, 0.1, 0.995


class Detector:
    def __init__(self, base_checkpoint: str, learn_seconds: float, seed: int = 0):
        ck = torch.load(base_checkpoint, map_location="cpu"); self.model = NCM(h=ck["h"], arch=ck["arch"]); self.model.load_state_dict(ck["state"], strict=False); self.model.eval()
        self.learn_seconds, self.seed = float(learn_seconds), seed
        self.state = "learning"; self.t0 = None; self.seen = 0; self.buf = []     # buffered (X, src, t) batches during learning
        self.threshold = None; self.src_state = {}                                # per source: z history, ewma, last flags, last alert time

    @property
    def learn_progress(self) -> float:
        if self.state != "learning" or self.t0 is None: return 1.0 if self.state == "shadow" else 0.0
        return min(1.0, (self.last_t - self.t0) / self.learn_seconds)

    def process(self, X, src, t):
        """Feed windows sorted by time. Returns a list of events (alerts and shadow blocks) once the detector is in shadow mode."""
        if len(X) == 0: return []
        self.seen += len(X); self.last_t = float(t.max())
        if self.state == "learning":
            self.t0 = float(t.min()) if self.t0 is None else self.t0; self.buf.append((X, src, t))
            if self.last_t - self.t0 >= self.learn_seconds: self._refit()
            return []
        return self._score(X, src, t)

    def _km(self, a, k):
        return torch.from_numpy(MiniBatchKMeans(int(min(k, max(2, len(a) // 2))), n_init=3, random_state=self.seed).fit(a).cluster_centers_.astype(np.float32))

    def _refit(self):
        X = np.concatenate([b[0] for b in self.buf]).astype(np.float32); src = np.concatenate([b[1] for b in self.buf]); t = np.concatenate([b[2] for b in self.buf]); self.buf = []
        cut = self.t0 + 0.8 * (self.last_t - self.t0); fit, cal = t < cut, t >= cut
        if fit.sum() < 50 or cal.sum() < 20: raise RuntimeError("not enough windows in the learning period to refit; extend it")
        m = self.model; m.mean.copy_(torch.from_numpy(X[fit].mean(0))); m.std.copy_(torch.from_numpy(X[fit].std(0) + 1e-3))
        day = np.zeros(len(X), np.int64); seqs = sequences(day, src, t); _, S = score(m, X, seqs); prev = np.zeros_like(S)
        for idx in seqs: prev[idx[1:]] = S[idx[:-1]]
        m.codebook.data = self._km(m.normalize(torch.from_numpy(X[fit])).numpy(), 512); m.state_codebook.data = self._km(S[fit], 512)
        with torch.no_grad(): comp = m.components(m.normalize(torch.from_numpy(X)), torch.from_numpy(S), torch.from_numpy(prev)).numpy()
        m.calib.copy_(torch.from_numpy(np.stack([comp[cal].mean(0), comp[cal].std(0)], 1)))
        sc = ewma(m.surprise(torch.from_numpy(comp)).numpy(), seqs); self.threshold = float(np.quantile(sc[cal], PCT)); self.state = "shadow"

    @torch.no_grad()
    def _score(self, X, src, t):
        events = []; m = self.model
        for s in np.unique(src):
            rows = np.flatnonzero(src == s); rows = rows[np.argsort(t[rows])]
            st = self.src_state.setdefault(int(s), {"z": np.zeros((0, X.shape[1]), np.float32), "ewma": None, "flags": [], "last_alert": -1e18, "last_block": -1e18})
            z = m.normalize(torch.from_numpy(X[rows].astype(np.float32))); hist = torch.from_numpy(st["z"]); allz = torch.cat([hist, z])[None]
            states = m.states(allz)[0]; prev = torch.cat([torch.zeros_like(states[:1]), states[:-1]])
            comp = m.components(allz[0], states, prev)[len(hist):]; v = m.surprise(comp).numpy()
            for i, vi in enumerate(v):
                st["ewma"] = vi if st["ewma"] is None else EWMA_A * vi + (1 - EWMA_A) * st["ewma"]
                st["flags"] = (st["flags"] + [bool(st["ewma"] > self.threshold)])[-3:]; ti = float(t[rows[i]])
                if sum(st["flags"]) >= 2:
                    if ti - st["last_alert"] > 60:
                        events.append({"kind": "alert", "src": int(s), "window_start": ti, "score": float(st["ewma"]), "detail": {"threshold": self.threshold}}); st["last_alert"] = ti
                    if ti - st["last_block"] > 600:
                        events.append({"kind": "shadow_block", "src": int(s), "window_start": ti, "score": float(st["ewma"]), "ttl_seconds": 3600, "detail": {"rule": "2 of last 3 windows above threshold"}}); st["last_block"] = ti
            st["z"] = torch.cat([hist, z])[-(HISTORY - 1):].numpy()
        return events
