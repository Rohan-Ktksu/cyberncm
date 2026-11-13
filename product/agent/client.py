"""Agent side of the console API: key pair, enrolment, signed requests."""
import hashlib, json, os, time, urllib.request
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

VERSION = "0.1"


def message(agent_id: str, ts: str, seq: str, body: bytes) -> bytes:
    return b"|".join([agent_id.encode(), ts.encode(), seq.encode(), hashlib.sha256(body).hexdigest().encode()])   # same as server/security.py


class UrllibTransport:
    """POST JSON with the standard library. A test can pass any object with the same post() method."""
    def __init__(self, base: str): self.base = base.rstrip("/")

    def post(self, path: str, body: bytes, headers: dict):
        req = urllib.request.Request(self.base + path, data=body, headers={"content-type": "application/json", **headers}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as r: return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e: return e.code, {"error": e.read().decode()[:300]}


class Client:
    def __init__(self, config_path: str, transport=None):
        self.path = config_path; self.cfg = json.load(open(config_path)) if os.path.exists(config_path) else {}
        self.transport = transport or (UrllibTransport(self.cfg["server"]) if self.cfg.get("server") else None)

    def _save(self):
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f: json.dump(self.cfg, f)

    def enrol(self, server: str, token: str) -> dict:
        key = Ed25519PrivateKey.generate(); pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
        priv = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()).hex()
        self.transport = self.transport or UrllibTransport(server)
        code, out = self.transport.post("/api/agent/enrol", json.dumps({"token": token, "public_key": pub, "agent_version": VERSION}).encode(), {})
        if code != 200: raise RuntimeError(f"enrolment refused ({code}): {out}")
        self.cfg = {"server": server, "agent_id": out["agent_id"], "site_id": out["site_id"], "private_key": priv, "seq": 0}; self._save(); return out

    def signed_post(self, path: str, obj: dict):
        body = json.dumps(obj).encode(); self.cfg["seq"] = int(self.cfg["seq"]) + 1; ts = str(time.time())
        key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self.cfg["private_key"])); sig = key.sign(message(self.cfg["agent_id"], ts, str(self.cfg["seq"]), body)).hex()
        self._save()
        return self.transport.post(path, body, {"x-agent": self.cfg["agent_id"], "x-ts": ts, "x-seq": str(self.cfg["seq"]), "x-sig": sig})

    def directive_signature(self, event: dict) -> str:
        """Signature of one 'would block' directive, so a recipient can check which agent issued it."""
        key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self.cfg["private_key"]))
        return key.sign(json.dumps({"site_id": self.cfg["site_id"], "src": event["src"], "window_start": event["window_start"], "action": "SHADOW_BLOCK", "ttl_seconds": event.get("ttl_seconds", 3600)}, sort_keys=True).encode()).hex()
