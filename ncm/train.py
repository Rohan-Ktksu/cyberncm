"""Train the NCM backbone on Monday (benign only). Usage: python train.py [gru|tf] [hidden] [seed]"""
import sys
import numpy as np
import torch
from sklearn.cluster import MiniBatchKMeans
from ncm import NCM, score, sequences

ARCH = sys.argv[1] if len(sys.argv) > 1 else "gru"
H = int(sys.argv[2]) if len(sys.argv) > 2 else 64
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 0
L = 64  # training chunk length (windows)
torch.manual_seed(SEED)
np.random.seed(SEED)
torch.set_num_threads(4)

z = np.load("data/windows.npz")
X, day, src, t = z["X"], z["day"], z["src"], z["t"]
mon = day == 0
cut = np.quantile(t[mon], 0.8)  # last 20% of Monday = calibration, never trained on
train, cal = mon & (t < cut), mon & (t >= cut)


def kmeans(a, k):
    return torch.from_numpy(MiniBatchKMeans(k, n_init=3, random_state=SEED).fit(a).cluster_centers_.astype(np.float32))


model = NCM(h=H, arch=ARCH)
model.mean.copy_(torch.from_numpy(X[train].mean(0)))
model.std.copy_(torch.from_numpy(X[train].std(0) + 1e-3))
model.codebook.copy_(kmeans(model.normalize(torch.from_numpy(X[train])).numpy(), len(model.codebook)))


def chunks(mask):
    """Fixed-length training chunks with a padding mask."""
    idx = np.flatnonzero(mask)
    xs, ms = [], []
    for s in sequences(day[idx], src[idx], t[idx]):
        s = idx[s]
        for i in range(0, max(len(s) - L // 2, 1), L // 2):
            c = s[i:i + L]
            x = np.zeros((L, X.shape[1]), np.float32)
            m = np.zeros(L, np.float32)
            x[:len(c)], m[:len(c)] = X[c], 1
            xs.append(x)
            ms.append(m)
    return torch.from_numpy(np.stack(xs)), torch.from_numpy(np.stack(ms))


xtr, mtr = chunks(train)
xva, mva = chunks(cal)
backbone = [p for n, p in model.named_parameters() if not n.startswith("stage")]
opt = torch.optim.AdamW(backbone, 2e-3, weight_decay=1e-2)


def loss_of(x, m):
    comp, _ = model(x)
    return ((comp[..., 2] / model.d + comp[..., 3]) * m).sum() / m.sum()  # Gaussian + token prediction loss


best, best_state, bad = 1e9, None, 0
for epoch in range(60):
    model.train()
    for b in torch.randperm(len(xtr)).split(32):
        opt.zero_grad()
        loss_of(xtr[b], mtr[b]).backward()
        torch.nn.utils.clip_grad_norm_(backbone, 1.0)
        opt.step()
    model.eval()
    with torch.no_grad():
        va = loss_of(xva, mva).item()
    if va < best - 1e-3:
        best, best_state, bad = va, {k: v.clone() for k, v in model.state_dict().items()}, 0
    else:
        bad += 1
        if bad == 6:
            break
model.load_state_dict(best_state)

# benign state vocabulary, then benign statistics of the four components
seqs = sequences(day, src, t)
_, S = score(model, X, seqs)
model.state_codebook.copy_(kmeans(S[train], len(model.state_codebook)))
comp, _ = score(model, X, seqs)
model.calib.copy_(torch.from_numpy(np.stack([comp[cal].mean(0), comp[cal].std(0)], 1)))

out = f"artifacts/ncm_{ARCH}{H}_s{SEED}.pt"
torch.save({"state": model.state_dict(), "arch": ARCH, "h": H, "cut": float(cut)}, out)
print(f"{out}: {int(train.sum())} train windows, {len(xtr)} chunks, {epoch + 1} epochs, validation loss {best:.4f}")
