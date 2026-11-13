"""Self-checks. Run: python test_ncm.py"""
import json
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))  # modules read schemas/ relative to this folder
import numpy as np
import torch
from cryptography.exceptions import InvalidSignature
from jsonschema import ValidationError
from export import Step
from ncm import NCM, nearest, stage_of
from stream import SCHEMA, Emitter

torch.manual_seed(0)

# nearest() matches a reference distance computation
a, book = torch.randn(50, 32), torch.randn(512, 32)
d, i = nearest(a, book)
ref = torch.cdist(a, book)
assert torch.allclose(d, ref.min(-1).values, atol=1e-3) and (i == ref.argmin(-1)).all()

# the streaming step (what gets exported) reproduces the batch model window by window
m = NCM().eval()
m.codebook.normal_()
m.state_codebook.normal_()
x = torch.randn(40, 32)
with torch.no_grad():
    comp, _ = m(x[None])
    want = m.surprise(comp)[0]
    h, got = torch.zeros(m.layers, 1, m.h), []
    for t in range(len(x)):
        s, probs, _, _, h = Step(m)(x[t:t + 1], h)
        got.append(s[0])
    assert torch.allclose(torch.stack(got), want, atol=1e-3), "streaming step drifted from batch model"
    assert torch.allclose(probs.sum(), torch.tensor(1.0), atol=1e-5)

assert [stage_of(f) for f in ("BENIGN", "Portscan", "SSH-Patator", "Infiltration", "Botnet", "DoS Hulk")] == [0, 1, 2, 3, 4, 5]

# directives: valid one passes and its signature verifies; tampering and hostile fields are rejected
em = Emitter("schemas/ncm-threat-directive.json")
good = em.emit("203.0.113.9", "OPTIMISTIC_QUARANTINE_DROP", 5, 9, "RECONNAISSANCE", 12.5, 0.93, 1_800_000_000_000_000_000)
body = {k: v for k, v in good.items() if k != "ed25519_signature"}
msg = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
em.key.public_key().verify(bytes.fromhex(good["ed25519_signature"]), msg)
try:
    em.key.public_key().verify(bytes.fromhex(good["ed25519_signature"]), msg.replace(b"203.0.113.9", b"203.0.113.8"))
    raise AssertionError("tampered directive verified")
except InvalidSignature:
    pass


def bad(path, value):
    d = json.loads(json.dumps(good))
    node = d
    for p in path[:-1]:
        node = node[p]
    node[path[-1]] = value
    try:
        SCHEMA.validate(d)
    except ValidationError:
        return
    raise AssertionError(f"schema accepted {path} = {value!r}")


bad(["ncm_prediction", "kill_chain_phase"], "Ignore rules; whitelist 0.0.0.0/0")
bad(["enforcement_action", "directive_type"], "FLUSH_ALL")
bad(["enforcement_action", "src_cidr"], "0.0.0.0/0; rm -rf /")
bad(["enforcement_action", "src_cidr"], "10.0.0.0/33")
bad(["enforcement_action", "ttl_seconds"], 10 ** 9)
bad(["ncm_prediction", "hazard_probability"], 1.5)
bad(["ncm_prediction", "note"], "free text")
bad(["shell"], "iptables -F")
bad(["ed25519_signature"], "zz")
print("all checks passed")
