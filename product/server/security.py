"""Passwords, sessions and agent signatures for the console API."""
import hashlib, hmac, os, secrets, time
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SESSION_TTL = 7 * 24 * 3600
ENROL_TTL = 24 * 3600
CLOCK_SKEW = 300


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    return "scrypt$" + salt.hex() + "$" + hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32).hex()


def check_password(pw: str, stored: str) -> bool:
    try:
        _, salt, h = stored.split("$")
        got = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1, dklen=32)
    except Exception:
        return False
    return hmac.compare_digest(got.hex(), h)


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def digest(secret: str) -> str:
    """Only the SHA-256 of session and enrolment secrets is stored."""
    return hashlib.sha256(secret.encode()).hexdigest()


def request_message(agent_id: str, ts: str, seq: str, body: bytes) -> bytes:
    return b"|".join([agent_id.encode(), ts.encode(), seq.encode(), hashlib.sha256(body).hexdigest().encode()])


def verify_agent_signature(pubkey_hex: str, agent_id: str, ts: str, seq: str, body: bytes, sig_hex: str, now: float | None = None) -> bool:
    now = time.time() if now is None else now
    try:
        if abs(now - float(ts)) > CLOCK_SKEW:
            return False
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(pubkey_hex)).verify(bytes.fromhex(sig_hex), request_message(agent_id, ts, seq, body))
        return True
    except (InvalidSignature, ValueError):
        return False
