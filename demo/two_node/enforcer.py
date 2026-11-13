"""Enforcement point for the lab service: a userspace connection gate, not a host firewall.

The lab HTTP service listens on 127.0.0.1:LAB_PORT. Every accepted TCP connection is checked against the
active block table before any byte is read; a blocked source address gets an immediate TCP reset. Nothing
outside this one listener is affected: the Windows firewall, other ports and other interfaces are untouched.

Safety properties:
- only addresses on the lab allowlist can be blocked; protected addresses never;
- every block has an absolute expiry of at most MAX_BLOCK_SECONDS, checked on every connection, so an
  expired block stops applying even if the reaper thread stalls;
- a repeated block request for an active target is a no-op (no extension);
- blocks live in this process's memory; a journal on disk records them, and on start-up every journalled
  block from a previous run is cleared, never restored. A crash therefore cannot leave a demo block behind.
"""
import json
import os
import socket
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import config
from policy import target_allowed


class Enforcer:
    def __init__(self, journal: Path, allowlist=config.LAB_CLIENT_ALLOWLIST, max_ttl=config.MAX_BLOCK_SECONDS,
                 lab_port=config.LAB_PORT, clock=None, on_event=None, duration_clock=None):
        self.journal, self.allowlist, self.max_ttl = journal, allowlist, max_ttl
        self.lab_port, self.clock = lab_port, clock or time.time
        # Wall time is for evidence timestamps; durations must survive clock corrections.
        self.duration_clock = duration_clock or clock or time.monotonic
        self.on_event = on_event or (lambda e: None)
        self.lock = threading.Lock()
        self.blocks = {}          # ip -> {created, expires, ttl, event_id, approval_mode, reason}
        self.drops = {}           # ip -> connections reset
        self._stop_event = threading.Event()
        self.startup_cleared = self._clear_previous_run()

    # ---- journal -------------------------------------------------------------------------------
    def _clear_previous_run(self):
        stale = []
        if self.journal.exists():
            try:
                stale = list(json.loads(self.journal.read_text()).get("blocks", {}).keys())
            except (ValueError, OSError):
                stale = ["<unreadable journal>"]
        self._write_journal()
        return stale

    def _write_journal(self):
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.journal.with_suffix(".tmp")
        tmp.write_text(json.dumps({"pid": os.getpid(), "blocks": self.blocks}))
        os.replace(tmp, self.journal)

    # ---- operations ----------------------------------------------------------------------------
    def block(self, ip, ttl, *, event_id, approval_mode, reason):
        ok, why = target_allowed(ip, self.allowlist)
        if not ok:
            self.on_event({"type": "block_refused", "target": ip, "reason": why})
            return {"ok": False, "error": why}
        if not isinstance(ttl, int) or not 1 <= ttl <= self.max_ttl:
            return {"ok": False, "error": f"ttl must be 1..{self.max_ttl} s"}
        now = self.clock()
        with self.lock:
            cur = self.blocks.get(ip)
            if cur and cur["deadline"] > self.duration_clock():
                return {"ok": True, "already": True, **cur}
            entry = {"target": ip, "created": now, "expires": now + ttl, "deadline": self.duration_clock() + ttl, "ttl": ttl, "event_id": event_id,
                     "approval_mode": approval_mode, "reason": reason,
                     "scope": {"service": "lab-http", "dst": f"{config.HOST}:{self.lab_port}", "proto": "tcp"}}
            self.blocks[ip] = entry
            self._write_journal()
        self.on_event({"type": "block_applied", **entry})
        return {"ok": True, "already": False, **entry}

    def unblock(self, ip=None, why="manual"):
        with self.lock:
            gone = [k for k in self.blocks if ip is None or k == ip]
            entries = [self.blocks.pop(k) for k in gone]
            self._write_journal()
        for e in entries:
            self.on_event({"type": "block_removed", "target": e["target"], "reason": why, "event_id": e["event_id"]})
        return gone

    def reap(self):
        now = self.clock()
        with self.lock:
            gone = [k for k, v in self.blocks.items() if v["deadline"] <= self.duration_clock()]
            entries = [self.blocks.pop(k) for k in gone]
            if gone:
                self._write_journal()
        for e in entries:
            self.on_event({"type": "block_removed", "target": e["target"], "reason": "expired", "event_id": e["event_id"]})
        return gone

    def is_blocked(self, ip) -> bool:
        with self.lock:
            cur = self.blocks.get(ip)
            return bool(cur and cur["deadline"] > self.duration_clock())

    def active(self):
        now = self.clock()
        with self.lock:
            return [dict(v, remaining=round(max(0.0, v["deadline"] - self.duration_clock()), 1))
                    for v in self.blocks.values() if v["deadline"] > self.duration_clock()]

    def total_drops(self) -> int:
        with self.lock:
            return sum(self.drops.values())

    def drops_by_ip(self) -> dict:
        with self.lock:
            return dict(self.drops)

    def count_drop(self, ip):
        with self.lock:
            self.drops[ip] = self.drops.get(ip, 0) + 1

    def start_reaper(self, period=0.25):
        self._stop_event.clear()
        def loop():
            while not self._stop_event.wait(period):
                self.reap()
        threading.Thread(target=loop, daemon=True, name="reaper").start()

    def stop_reaper(self):
        self._stop_event.set()


class _LabHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"service": "cyberncm lab HTTP service", "client": self.client_address[0],
                           "time": time.time()}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class LabGate(ThreadingHTTPServer):
    """The isolated lab service. verify_request runs right after accept(), before any request byte is read."""
    allow_reuse_address = False   # on Windows SO_REUSEADDR would let a second instance share the port
    daemon_threads = True

    def __init__(self, enforcer: Enforcer, host=config.HOST, port=config.LAB_PORT):
        self.enforcer = enforcer
        super().__init__((host, port), _LabHandler)

    def verify_request(self, request, client_address):
        if self.enforcer.is_blocked(client_address[0]):
            self.enforcer.count_drop(client_address[0])
            try:   # linger 0 -> close sends RST: the client sees "connection reset", not a slow timeout
                request.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("hh", 1, 0))
            except OSError:
                pass
            return False
        return True
