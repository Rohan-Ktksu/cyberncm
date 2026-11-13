"""Signed alert format shared by both nodes: build, sign, verify.

Serialization is the one ncm/stream.py already uses: Ed25519 over json.dumps(body, sort_keys=True,
separators=(",", ":")) where body is the message without ed25519_signature. Floats are rounded before
signing. This is still not RFC 8785; a non-Python verifier would need a JCS library.
"""
import hashlib
import json
import os
import threading
import time
import uuid
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption
from jsonschema import Draft202012Validator

import config

SCHEMA = Draft202012Validator(json.loads(config.SCHEMA_FILE.read_text()))
VERSION = "1.2.0"


def canonical(body: dict) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


def node_id_for(pub_raw: bytes) -> str:
    return "urn:ietf:params:rats:dice:" + hashlib.sha256(pub_raw).hexdigest()


def pub_raw(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:            # read only
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_or_create_key(path: Path) -> Ed25519PrivateKey:
    if path.exists():
        return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(path.read_text().strip()))
    key = Ed25519PrivateKey.generate()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex())
    return key


def _atomic_write(path: Path, data: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(data)
    os.replace(tmp, path)


class Sender:
    """Signs alerts. The sequence number is persisted so a restarted node never reuses one."""

    def __init__(self, key: Ed25519PrivateKey, seq_file: Path):
        self.key = key
        self.node_id = node_id_for(pub_raw(key))
        self.seq_file = seq_file
        self.seq = json.loads(seq_file.read_text())["last_seq"] if seq_file.exists() else 0
        self.lock = threading.Lock()

    def build(self, *, subject_ip, kill_chain_phase, surprise, hazard, token, next_token, model, detection,
              ttl_seconds=30, directive_type="OPTIMISTIC_QUARANTINE_DROP", dst_port=0, ip_proto=6,
              lifetime_s=90, now_ns=None):
        with self.lock:
            self.seq += 1
            _atomic_write(self.seq_file, json.dumps({"last_seq": self.seq}))
            seq = self.seq
        now_ns = time.time_ns() if now_ns is None else now_ns
        msg = {
            "schema_version": VERSION, "node_id": self.node_id, "shard_id": 0,
            "timestamp_ns": now_ns, "expires_ns": now_ns + int(lifetime_s * 1e9),
            "monotonic_seq": seq, "event_id": uuid.uuid4().hex,
            "rats_attestation_quote_sha256": model["onnx_sha256"],   # placeholder for attestation: model file hash
            "ncm_prediction": {
                "current_state_token": int(token), "predicted_next_token": int(next_token),
                "kill_chain_phase": kill_chain_phase,
                "surprise_score": round(float(min(max(surprise, 0.0), 50.0)), 3),
                "hazard_probability": round(float(hazard), 4), "horizon_ms": 5000},
            "enforcement_action": {"directive_type": directive_type, "src_cidr": f"{subject_ip}/32",
                                   "dst_port": int(dst_port), "ip_proto": int(ip_proto), "ttl_seconds": int(ttl_seconds)},
            "model": dict(model),
            "detection": {k: (round(float(v), 6) if isinstance(v, float) else v) for k, v in detection.items()},
        }
        return self.sign(msg)

    def sign(self, msg: dict) -> dict:
        body = {k: v for k, v in msg.items() if k != "ed25519_signature"}
        out = dict(body)
        out["ed25519_signature"] = self.key.sign(canonical(body)).hex()
        SCHEMA.validate(out)     # a message that does not fit the schema is never sent
        return out


class Rejected(Exception):
    def __init__(self, code, detail):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


class Verifier:
    """Checks, in order: schema, known sender, signature, authorization, freshness/expiry, scope, replay.

    Replay state (last sequence number per sender, event ids seen and not yet expired) is persisted, and only
    updated after a message passes every other check, so unsigned garbage cannot poison it.
    """

    def __init__(self, trust: dict, state_file: Path, lab_port: int = config.LAB_PORT):
        self.trust = trust
        self.state_file = state_file
        self.lab_port = lab_port
        self.lock = threading.Lock()
        st = json.loads(state_file.read_text()) if state_file.exists() else {}
        self.last_seq = dict(st.get("last_seq", {}))
        self.seen = dict(st.get("seen", {}))      # event_id -> expires_ns

    def _persist(self):
        _atomic_write(self.state_file, json.dumps({"last_seq": self.last_seq, "seen": self.seen}))

    def verify(self, msg, now_ns=None) -> dict:
        now_ns = time.time_ns() if now_ns is None else now_ns
        if not isinstance(msg, dict):
            raise Rejected("schema", "message is not a JSON object")
        errors = sorted(SCHEMA.iter_errors(msg), key=lambda e: list(e.path))
        if errors:
            raise Rejected("schema", errors[0].message[:200])
        sender = self.trust.get(msg["node_id"])
        if sender is None:
            raise Rejected("unknown_sender", "node_id is not in the trusted-sender list")
        pub = bytes.fromhex(sender["public_key_hex"])
        if node_id_for(pub) != msg["node_id"]:
            raise Rejected("unknown_sender", "trusted entry does not match node_id")
        body = {k: v for k, v in msg.items() if k != "ed25519_signature"}
        try:
            Ed25519PublicKey.from_public_bytes(pub).verify(bytes.fromhex(msg["ed25519_signature"]), canonical(body))
        except (InvalidSignature, ValueError):
            raise Rejected("bad_signature", "Ed25519 signature does not verify (tampered or wrong key)")
        if "alert" not in sender.get("allowed", []):
            raise Rejected("not_authorized", "sender is not authorized to send alerts")
        if msg["timestamp_ns"] > now_ns + config.CLOCK_SKEW_S * 1e9:
            raise Rejected("not_fresh", "timestamp is in the future beyond the allowed skew")
        if msg["expires_ns"] <= now_ns:
            raise Rejected("expired", "expires_ns has passed")
        life = msg["expires_ns"] - msg["timestamp_ns"]
        if life <= 0 or life > config.MAX_ALERT_LIFETIME_S * 1e9:
            raise Rejected("bad_expiry", "lifetime must be between 0 and %d s" % config.MAX_ALERT_LIFETIME_S)
        ea = msg["enforcement_action"]
        if ea["ip_proto"] != 6 or ea["dst_port"] not in (0, self.lab_port):
            raise Rejected("scope", "only TCP to any port or to the lab service port is in scope")
        with self.lock:
            if msg["event_id"] in self.seen:
                raise Rejected("replay", "event_id already received")
            if msg["monotonic_seq"] <= self.last_seq.get(msg["node_id"], 0):
                raise Rejected("replay", "monotonic_seq %d not above last accepted %d"
                               % (msg["monotonic_seq"], self.last_seq.get(msg["node_id"], 0)))
            self.last_seq[msg["node_id"]] = msg["monotonic_seq"]
            self.seen = {k: v for k, v in self.seen.items() if v > now_ns}   # forget expired ids
            self.seen[msg["event_id"]] = msg["expires_ns"]
            self._persist()
        return {"sender_name": sender.get("name", ""), "expected_model_onnx_sha256": sender.get("expected_model_onnx_sha256")}


def load_trust(path: Path = config.TRUST_FILE) -> dict:
    return json.loads(path.read_text())
