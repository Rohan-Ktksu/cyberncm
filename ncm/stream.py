"""Replay one day through the FP32 model as a live node would, and emit signed NCMThreatDirectives.

Usage: python stream.py CHECKPOINT [day 1-4, default 4 = Friday]
Writes artifacts/directives_<day>.jsonl and artifacts/demo_events_<day>.json (the console's event format).
"""
import hashlib
import ipaddress
import json
from pathlib import Path
import sys
import time
import numpy as np
import onnxruntime as ort
import torch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from jsonschema import Draft202012Validator
from ncm import EWMA, STAGES

W = 5.0   # window length, seconds
TTL = 30  # optimistic rules expire after 30 s unless consensus promotes them
PROTECTED = [ipaddress.ip_network("192.168.10.3/32")]  # the lab's DNS server: never block
SCHEMA = Draft202012Validator(json.load(open("schemas/ncm-threat-directive.json")))


class Emitter:
    """Builds a directive from fixed fields, validates it against the schema, signs it."""

    def __init__(self, model_path):
        self.key = Ed25519PrivateKey.generate()  # demo key; a real node uses its TPM/DICE-held key
        pub = self.key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.node_id = "urn:ietf:params:rats:dice:" + hashlib.sha256(pub).hexdigest()
        # placeholder for the attestation quote: hash of the model file this node runs
        self.quote = hashlib.sha256(open(model_path, "rb").read()).hexdigest()
        self.seq = 0

    def emit(self, src, kind, token, next_token, stage, surprise, hazard, ts_ns):
        self.seq += 1
        d = {
            "schema_version": "1.1.0", "node_id": self.node_id, "shard_id": 0, "timestamp_ns": ts_ns,
            "monotonic_seq": self.seq, "rats_attestation_quote_sha256": self.quote,
            "ncm_prediction": {
                "current_state_token": token, "predicted_next_token": next_token, "kill_chain_phase": stage,
                "surprise_score": round(float(np.clip(surprise, 0, 50)), 3),
                "hazard_probability": round(float(hazard), 4), "horizon_ms": int(W * 1000)},
            "enforcement_action": {"directive_type": kind, "src_cidr": f"{src}/32", "dst_port": 0, "ip_proto": 6,
                                   "ttl_seconds": TTL},
        }
        # shortcut: sorted compact JSON, not full RFC 8785 number formatting; switch to a JCS library
        # before a second implementation (the Rust agent) has to verify these signatures
        d["ed25519_signature"] = self.key.sign(json.dumps(d, sort_keys=True, separators=(",", ":")).encode()).hex()
        SCHEMA.validate(d)  # a directive that does not fit the schema is never sent
        return d


def main(ckpt, d):
    model_path = str(Path(ckpt).with_suffix(".onnx"))
    if not Path(model_path).is_file():
        raise FileNotFoundError(f"FP32 export required: {model_path}. Run export.py for this checkpoint; INT8 is experimental and is not a fallback.")
    thr = torch.load(ckpt)["thresholds"]
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1
    sess = ort.InferenceSession(model_path, opts)
    layers, hdim = sess.get_inputs()[1].shape[0], sess.get_inputs()[1].shape[2]

    z = np.load("data/windows.npz")
    m = z["day"] == d
    X, src, t, fam = z["X"][m], z["src"][m], z["t"][m], z["family"][m]
    names = list(z["family_names"])
    ips, sid = np.unique(src, return_inverse=True)
    n = len(ips)
    H = np.zeros((layers, n, hdim), np.float32)       # hidden state per source
    s_avg, h_avg = np.full(n, np.nan), np.full(n, np.nan)  # smoothed surprise and hazard per source
    until = np.zeros((2, n))                           # active rule expiry per tier: rate limit, quarantine
    em = Emitter(model_path)
    t0_ns, t0 = time.time_ns(), t.min()
    directives, events = [], []
    covered = np.zeros(len(X), bool)                   # window fell under an active quarantine
    first_block, suppressed, busy = {}, 0, 0.0

    for now in np.unique(t):
        rows = np.flatnonzero(t == now)
        i = sid[rows]
        tic = time.perf_counter()
        surprise, probs, token, nxt, h_out = sess.run(None, {"x": X[rows], "h": H[:, i]})
        busy += time.perf_counter() - tic
        H[:, i] = h_out
        hz = 1 - probs[:, 0]
        s_avg[i] = np.where(np.isnan(s_avg[i]), surprise, EWMA * surprise + (1 - EWMA) * s_avg[i])
        h_avg[i] = np.where(np.isnan(h_avg[i]), hz, EWMA * hz + (1 - EWMA) * h_avg[i])
        risk = 0.5 * np.clip((s_avg[i] - thr["q50"]) / (thr["q999"] - thr["q50"]), 0, 1) + 0.5 * h_avg[i]
        covered[rows] = until[1, i] > now
        for j in np.flatnonzero(risk > thr["r_limit"]):
            s = i[j]
            tier = int(risk[j] > thr["r_block"])
            if until[tier:, s].max() > now:  # an equal or stronger rule is already active
                continue
            ip = ipaddress.ip_address(int(ips[s]))
            if any(ip in net for net in PROTECTED):
                suppressed += 1
                continue
            kind = ["OPTIMISTIC_RATE_LIMIT", "OPTIMISTIC_QUARANTINE_DROP"][tier]
            stage = STAGES[1 + int(probs[j, 1:].argmax())]
            ts_ns = t0_ns + int((now - t0) * 1e9)
            dct = em.emit(ip, kind, int(token[j]), int(nxt[j]), stage, s_avg[s], h_avg[s], ts_ns)
            until[tier, s] = now + TTL
            directives.append(dct)
            events.append({"seq": len(events) + 1, "t_ms": int((now - t0) * 1000), "node_id": em.node_id,
                           "type": "quarantine_applied" if tier else "rate_limit_applied",
                           "payload": {"src": str(ip), "phase": stage, "risk": round(float(risk[j]), 3),
                                       "truth": names[fam[rows[j]]]}})
            if tier:
                first_block.setdefault(s, now)

    day_name = ["mon", "tue", "wed", "thu", "fri"][d]
    with open(f"artifacts/directives_{day_name}.jsonl", "w") as f:
        f.writelines(json.dumps(x) + "\n" for x in directives)
    json.dump(events, open(f"artifacts/demo_events_{day_name}.json", "w"))

    atk = fam > 0
    attackers = {s for s in np.unique(sid[atk])}
    kinds = [x["enforcement_action"]["directive_type"] for x in directives]
    print(f"{day_name}: {len(X)} windows from {n} sources in {len(np.unique(t))} time steps; "
          f"model time {busy / len(np.unique(t)) * 1e3:.2f} ms per step")
    print(f"directives: {kinds.count('OPTIMISTIC_RATE_LIMIT')} rate-limit, "
          f"{kinds.count('OPTIMISTIC_QUARANTINE_DROP')} quarantine, {suppressed} suppressed for protected prefixes; "
          f"all schema-valid and signed")
    print(f"attack windows under an active quarantine: {covered[atk].mean():.1%}   "
          f"benign windows under an active quarantine: {covered[~atk].mean():.2%}")
    for s in sorted(attackers | set(first_block)):
        ip = ipaddress.ip_address(int(ips[s]))
        mine = sid == s
        fams = sorted({names[f] for f in fam[mine & atk]})
        if s in attackers:
            start = t[mine & atk].min()
            got = f"first quarantine {first_block[s] - start:+.0f} s after its first attack window" if s in first_block else "NEVER quarantined"
            print(f"  attacker {ip}: {', '.join(fams)}; {got}; "
                  f"{covered[mine & atk].mean():.0%} of its attack windows covered, "
                  f"{covered[mine & ~atk].mean() if (mine & ~atk).any() else 0:.0%} of its benign windows")
        else:
            print(f"  FALSE quarantine of benign source {ip}: {covered[mine].mean():.1%} of its {mine.sum()} windows")

    return {"windows": int(len(X)), "attack_windows": int(atk.sum()),
            "benign_windows": int((~atk).sum()),
            "attack_windows_covered": int(covered[atk].sum()),
            "benign_windows_covered": int(covered[~atk].sum()),
            "attack_coverage": float(covered[atk].mean()) if atk.any() else None,
            "benign_coverage": float(covered[~atk].mean()) if (~atk).any() else None}


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 4)
