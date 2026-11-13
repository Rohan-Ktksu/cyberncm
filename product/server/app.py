"""Console API for the single-site product. Run: uvicorn product.server.app:create_app --factory  (CYBERNCM_DB sets the database path; default ./cyberncm.db).
Scope: sign-up, sites, enrolment of one agent per site with an Ed25519 key, signed heartbeats and events, shadow-mode "would block" list. It never sends
a block to any device and it has no mesh features (gate G1, research/G1.md)."""
import json, os, re, time
from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .db import DB
from . import security as sec

CONSOLE = os.path.join(os.path.dirname(__file__), "..", "console")
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")
FAILS: dict[str, list[float]] = {}          # login failures per email (in memory)
ONLINE = 120                                 # seconds without a message before an agent is shown as offline


class Creds(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(min_length=10, max_length=200)


class NewSite(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class Enrol(BaseModel):
    token: str
    public_key: str = Field(min_length=64, max_length=64)    # Ed25519 raw public key, hex
    agent_version: str = Field(default="", max_length=40)


def create_app(db_path: str | None = None, public_url: str = "") -> FastAPI:
    db = DB(db_path or os.environ.get("CYBERNCM_DB", "cyberncm.db"))
    app = FastAPI(title="cyberncm console", docs_url=None, redoc_url=None)
    app.state.db = db

    def user_of(session: str | None = Cookie(default=None)):
        row = db.one("SELECT user_id, expires FROM sessions WHERE token_hash=?", (sec.digest(session or ""),)) if session else None
        if not row or row["expires"] < time.time():
            raise HTTPException(401, "not signed in")
        return row["user_id"]

    def start_session(resp: Response, user_id: int):
        tok = sec.new_secret(); db.execute("INSERT INTO sessions VALUES (?,?,?)", (sec.digest(tok), user_id, time.time() + sec.SESSION_TTL))
        resp.set_cookie("session", tok, httponly=True, samesite="strict", max_age=sec.SESSION_TTL, secure=public_url.startswith("https"))

    @app.post("/api/signup")
    def signup(c: Creds, resp: Response):
        if not EMAIL.match(c.email): raise HTTPException(400, "invalid email")
        if db.one("SELECT 1 FROM users WHERE email=?", (c.email.lower(),)): raise HTTPException(409, "email already registered")
        cur = db.execute("INSERT INTO users (email, pw_hash, created) VALUES (?,?,?)", (c.email.lower(), sec.hash_password(c.password), time.time()))
        start_session(resp, cur.lastrowid); return {"email": c.email.lower()}

    @app.post("/api/login")
    def login(c: Creds, resp: Response):
        e = c.email.lower(); recent = [t for t in FAILS.get(e, []) if t > time.time() - 600]
        if len(recent) >= 5: raise HTTPException(429, "too many attempts, try again later")
        row = db.one("SELECT id, pw_hash FROM users WHERE email=?", (e,))
        if not row or not sec.check_password(c.password, row["pw_hash"]):
            FAILS[e] = recent + [time.time()]; raise HTTPException(401, "wrong email or password")
        FAILS.pop(e, None); start_session(resp, row["id"]); return {"email": e}

    @app.post("/api/logout")
    def logout(resp: Response, session: str | None = Cookie(default=None)):
        if session: db.execute("DELETE FROM sessions WHERE token_hash=?", (sec.digest(session),))
        resp.delete_cookie("session"); return {}

    @app.get("/api/session")
    def session_info(session: str | None = Cookie(default=None)):
        """Who is signed in, without a 401 when nobody is (the page calls this on load)."""
        row = db.one("SELECT u.email e, s.expires x FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?", (sec.digest(session),)) if session else None
        return {"email": row["e"] if row and row["x"] > time.time() else None}

    @app.get("/api/me")
    def me(uid: int = Depends(user_of)):
        return {"email": db.one("SELECT email FROM users WHERE id=?", (uid,))["email"]}

    def status_of(site_id: int):
        a = db.one("SELECT * FROM agents WHERE site_id=?", (site_id,))
        if not a: return "waiting", None
        if a["last_seen"] is None or time.time() - a["last_seen"] > ONLINE: return "offline", a
        return (a["state"] or "learning"), a

    def mine(site_id: int, uid: int):
        s = db.one("SELECT * FROM sites WHERE id=? AND user_id=?", (site_id, uid))
        if not s: raise HTTPException(404, "no such site")        # also the answer for someone else's site
        return s

    def install_command(token: str, base: str) -> str:
        return (f"git clone https://github.com/Rohan-Ktksu/cyberncm && pip install -r cyberncm/requirements.txt && "
                f"python cyberncm/product/agent/agent.py enrol --server {base} --token {token}")

    @app.post("/api/sites")
    def add_site(s: NewSite, request: Request, uid: int = Depends(user_of)):
        tok = sec.new_secret(); cur = db.execute("INSERT INTO sites (user_id, name, created, enrol_hash, enrol_expires) VALUES (?,?,?,?,?)",
                                                  (uid, s.name.strip(), time.time(), sec.digest(tok), time.time() + sec.ENROL_TTL))
        base = public_url or str(request.base_url).rstrip("/")
        return {"id": cur.lastrowid, "name": s.name.strip(), "enrolment_token": tok, "expires_in_hours": sec.ENROL_TTL // 3600, "install_command": install_command(tok, base)}

    @app.get("/api/sites")
    def sites(uid: int = Depends(user_of)):
        out = []
        for s in db.all("SELECT * FROM sites WHERE user_id=? ORDER BY id", (uid,)):
            st, a = status_of(s["id"]); out.append({"id": s["id"], "name": s["name"], "status": st, "last_seen": a["last_seen"] if a else None})
        return out

    @app.get("/api/sites/{site_id}")
    def site(site_id: int, uid: int = Depends(user_of)):
        s = mine(site_id, uid); st, a = status_of(site_id); now = time.time()
        alerts = db.all("SELECT * FROM events WHERE site_id=? AND kind='alert' ORDER BY id DESC LIMIT 50", (site_id,))
        wb = db.all("SELECT * FROM events WHERE site_id=? AND kind='shadow_block' AND expires>? ORDER BY id DESC LIMIT 100", (site_id, now))
        return {"id": s["id"], "name": s["name"], "status": st, "mode": "shadow (nothing is blocked)",
                "agent": None if not a else {"id": a["id"], "last_seen": a["last_seen"], "windows_seen": a["windows_seen"], "learn_progress": a["learn_progress"], "info": json.loads(a["info"] or "{}")},
                "alerts_total": db.one("SELECT COUNT(*) c FROM events WHERE site_id=? AND kind='alert'", (site_id,))["c"],
                "recent_alerts": [{"src": e["src"], "window_start": e["window_start"], "score": e["score"], "received": e["received"]} for e in alerts],
                "would_block": [{"src": e["src"], "score": e["score"], "window_start": e["window_start"], "expires": e["expires"], "signature": e["signature"]} for e in wb]}

    @app.post("/api/agent/enrol")
    def enrol(e: Enrol):
        row = db.one("SELECT * FROM sites WHERE enrol_hash=?", (sec.digest(e.token),))
        if not row or row["enrol_used"] or row["enrol_expires"] < time.time(): raise HTTPException(403, "invalid, used or expired enrolment token")
        try: bytes.fromhex(e.public_key)
        except ValueError: raise HTTPException(400, "public key must be hex")
        agent_id = "ag_" + sec.new_secret()[:16]
        db.execute("INSERT INTO agents (id, site_id, pubkey, created, state) VALUES (?,?,?,?,?)", (agent_id, row["id"], e.public_key, time.time(), "learning"))
        db.execute("UPDATE sites SET enrol_used=1 WHERE id=?", (row["id"],)); return {"agent_id": agent_id, "site_id": row["id"], "site_name": row["name"]}

    async def signed(request: Request):
        body = await request.body(); aid = request.headers.get("x-agent", ""); a = db.one("SELECT * FROM agents WHERE id=?", (aid,))
        ts, seq, sig = request.headers.get("x-ts", ""), request.headers.get("x-seq", ""), request.headers.get("x-sig", "")
        if not a or not seq.isdigit() or not sec.verify_agent_signature(a["pubkey"], aid, ts, seq, body, sig): raise HTTPException(401, "bad signature")
        if int(seq) <= a["last_seq"]: raise HTTPException(409, "replayed or out of order request")
        db.execute("UPDATE agents SET last_seq=? WHERE id=?", (int(seq), aid)); return a, json.loads(body or b"{}")

    @app.post("/api/agent/heartbeat")
    async def heartbeat(request: Request):
        a, b = await signed(request); state = b.get("state") if b.get("state") in ("learning", "shadow") else "learning"
        db.execute("UPDATE agents SET last_seen=?, state=?, windows_seen=?, learn_progress=?, info=? WHERE id=?",
                   (time.time(), state, int(b.get("windows_seen", 0)), float(b.get("learn_progress", 0.0)), json.dumps(b.get("info", {}))[:2000], a["id"])); return {"ok": True}

    @app.post("/api/agent/events")
    async def events(request: Request):
        a, b = await signed(request); n = 0
        for ev in (b.get("events") or [])[:500]:
            kind = ev.get("kind")
            if kind not in ("alert", "shadow_block"): continue
            db.execute("INSERT INTO events (site_id, received, kind, src, window_start, score, expires, detail, signature) VALUES (?,?,?,?,?,?,?,?,?)",
                       (a["site_id"], time.time(), kind, str(ev.get("src", ""))[:64], float(ev.get("window_start", 0)), float(ev.get("score", 0)), time.time() + float(ev.get("ttl_seconds", 3600)) if kind == "shadow_block" else None,
                        json.dumps(ev.get("detail", {}))[:1000], str(ev.get("signature", ""))[:200])); n += 1
        db.execute("UPDATE agents SET last_seen=? WHERE id=?", (time.time(), a["id"])); return {"stored": n}

    @app.get("/")
    def index(): return FileResponse(os.path.join(CONSOLE, "index.html"))
    app.mount("/static", StaticFiles(directory=CONSOLE), name="static")
    return app


# uvicorn product.server.app:create_app --factory   (reads CYBERNCM_DB, default ./cyberncm.db)
