"""Tests for the single-site product. Run from the repository root: python -m pytest product/tests -q
The end-to-end test needs torch and scikit-learn (the agent's detector) and takes a few minutes."""
import json, os, sys, time
import pytest
from fastapi.testclient import TestClient

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "product", "agent"))
os.environ["CYBERNCM_NO_DEFAULT_APP"] = "1"
from product.server.app import create_app          # noqa: E402
from product.server import security as sec          # noqa: E402

PW = "correct horse battery"


class AsTransport:
    """Lets the agent client talk to a TestClient instead of the network."""
    def __init__(self, c): self.c = c
    def post(self, path, body, headers):
        r = self.c.post(path, content=body, headers={"content-type": "application/json", **headers}); return r.status_code, r.json()


@pytest.fixture()
def app(tmp_path): return create_app(str(tmp_path / "t.db"), public_url="http://console.test")


def signed_in(app, email="a@example.com"):
    c = TestClient(app); assert c.post("/api/signup", json={"email": email, "password": PW}).status_code == 200; return c


def test_password_hash_and_check():
    h = sec.hash_password(PW); assert h != PW and sec.check_password(PW, h) and not sec.check_password(PW + "x", h) and not sec.check_password(PW, "garbage")
    assert sec.hash_password(PW) != h                      # salted


def test_signup_validation_login_and_lockout(app):
    c = TestClient(app)
    assert c.post("/api/signup", json={"email": "not-an-email", "password": PW}).status_code == 400
    assert c.post("/api/signup", json={"email": "a@example.com", "password": "short"}).status_code == 422
    assert c.post("/api/signup", json={"email": "a@example.com", "password": PW}).status_code == 200
    assert c.post("/api/signup", json={"email": "A@example.com", "password": PW}).status_code == 409      # case-insensitive
    c2 = TestClient(app); assert c2.get("/api/me").status_code == 401 and c2.get("/api/session").json() == {"email": None}
    assert c.get("/api/session").json() == {"email": "a@example.com"}
    for _ in range(5): assert c2.post("/api/login", json={"email": "a@example.com", "password": "wrong password!"}).status_code == 401
    assert c2.post("/api/login", json={"email": "a@example.com", "password": PW}).status_code == 429       # locked after 5 failures


def test_sites_are_private_to_their_owner(app):
    a = signed_in(app, "a@example.com"); b = signed_in(app, "b@example.com")
    site = a.post("/api/sites", json={"name": "HQ"}).json()
    assert a.get(f"/api/sites/{site['id']}").status_code == 200
    assert b.get(f"/api/sites/{site['id']}").status_code == 404 and b.get("/api/sites").json() == []
    assert TestClient(app).get(f"/api/sites/{site['id']}").status_code == 401


def test_enrolment_token_single_use_and_expiry(app):
    from client import Client
    c = signed_in(app); s = c.post("/api/sites", json={"name": "HQ"}).json(); tok = s["enrolment_token"]
    assert "enrol --server http://console.test --token " + tok in s["install_command"]
    import tempfile; d = tempfile.mkdtemp()
    cl = Client(os.path.join(d, "a.json"), AsTransport(c)); cl.enrol("http://console.test", tok)
    with pytest.raises(RuntimeError): Client(os.path.join(d, "b.json"), AsTransport(c)).enrol("http://console.test", tok)         # used
    s2 = c.post("/api/sites", json={"name": "Branch"}).json(); app.state.db.execute("UPDATE sites SET enrol_expires=? WHERE id=?", (time.time() - 1, s2["id"]))
    with pytest.raises(RuntimeError): Client(os.path.join(d, "c.json"), AsTransport(c)).enrol("http://console.test", s2["enrolment_token"])     # expired
    with pytest.raises(RuntimeError): Client(os.path.join(d, "d.json"), AsTransport(c)).enrol("http://console.test", "not-a-token")


def test_signed_requests_replay_and_tampering(app, tmp_path):
    from client import Client
    c = signed_in(app); s = c.post("/api/sites", json={"name": "HQ"}).json()
    cl = Client(str(tmp_path / "a.json"), AsTransport(c)); cl.enrol("http://console.test", s["enrolment_token"])
    assert cl.signed_post("/api/agent/heartbeat", {"state": "learning", "windows_seen": 5, "learn_progress": 0.1})[0] == 200
    # replay of the same sequence number
    cl.cfg["seq"] -= 1
    assert cl.signed_post("/api/agent/heartbeat", {"state": "learning"})[0] == 409
    # tampered body: sign one body, send another
    cl.cfg["seq"] += 5; body = json.dumps({"state": "shadow"}).encode()
    import hashlib; from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; from client import message
    ts = str(time.time()); sig = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(cl.cfg["private_key"])).sign(message(cl.cfg["agent_id"], ts, str(cl.cfg["seq"]), body)).hex()
    code, _ = AsTransport(c).post("/api/agent/heartbeat", json.dumps({"state": "learning", "x": 1}).encode(), {"x-agent": cl.cfg["agent_id"], "x-ts": ts, "x-seq": str(cl.cfg["seq"]), "x-sig": sig}); assert code == 401
    # a stale timestamp is refused
    assert not sec.verify_agent_signature("00" * 32, "ag", "1.0", "1", b"{}", "00" * 64)
    # status as the console sees it
    d = c.get(f"/api/sites/{s['id']}").json(); assert d["status"] == "learning" and d["agent"]["windows_seen"] == 5 and d["mode"].startswith("shadow")


def test_end_to_end_signup_to_shadow_alerts(app, tmp_path):
    pytest.importorskip("torch"); pytest.importorskip("sklearn")
    for _p in (("product", "sample", "flows_sample.csv.gz"), ("product", "agent", "model", "base_gru64.pt")):
        if not os.path.exists(os.path.join(ROOT, *_p)):
            pytest.skip("sample flows and model checkpoint are not published; see the README")
    from client import Client
    import agent as agent_mod
    c = signed_in(app); site = c.post("/api/sites", json={"name": "Head office"}).json()
    assert c.get("/api/sites").json()[0]["status"] == "waiting"
    cl = Client(str(tmp_path / "agent.json"), AsTransport(c)); cl.enrol("http://console.test", site["enrolment_token"])
    assert c.get("/api/sites").json()[0]["status"] in ("learning", "waiting", "offline", "shadow")
    sample = os.path.join(ROOT, "product", "sample", "flows_sample.csv.gz")
    det = agent_mod.run(cl, sample, learn_minutes=20, log=lambda *_: None)
    assert det.state == "shadow" and det.threshold is not None
    d = c.get(f"/api/sites/{site['id']}").json()
    assert d["status"] == "shadow" and d["agent"]["windows_seen"] > 1000 and d["alerts_total"] > 0
    blocked = {w["src"] for w in d["would_block"]}; assert "172.16.0.1" in blocked, blocked      # the FTP brute-force attacker of the sample
    assert all(w["signature"] for w in d["would_block"]) and d["mode"].startswith("shadow")
    print("would block:", sorted(blocked), "alerts:", d["alerts_total"])
