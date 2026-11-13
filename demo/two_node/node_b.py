"""Simulated Site B (Node B): independent verifier, policy gate, lab HTTP enforcer, probe runner, and dashboard.

Everything runs on 127.0.0.1. Windows host firewall and public networking are never touched.
"""
import argparse
import atexit
import http.client
import json
import signal
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import config
import policy
import report
from bootstrap import ensure_setup
from enforcer import Enforcer, LabGate
from protocol import Rejected, Verifier, load_or_create_key, load_trust, node_id_for, pub_raw


def http_probe(src_ip: str, host: str = config.HOST, port: int = config.LAB_PORT, timeout: float = 1.5) -> dict:
    """Execute a real TCP + HTTP GET request bound to src_ip -> host:port."""
    t0 = time.perf_counter()
    conn = None
    try:
        conn = http.client.HTTPConnection(host, port, timeout=timeout, source_address=(src_ip, 0))
        conn.request("GET", "/")
        resp = conn.getresponse()
        body = resp.read().decode(errors="replace")
        ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "ts": time.time(),
            "source_ip": src_ip,
            "target": f"http://{host}:{port}/",
            "ok": resp.status == 200,
            "http_status": resp.status,
            "error": None,
            "latency_ms": ms,
            "body_preview": body[:120],
        }
    except Exception as e:
        ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "ts": time.time(),
            "source_ip": src_ip,
            "target": f"http://{host}:{port}/",
            "ok": False,
            "http_status": None,
            "error": f"{type(e).__name__}: {e}",
            "latency_ms": ms,
            "body_preview": None,
        }
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


class NodeBState:
    def __init__(self, *, node_id: str, verifier: Verifier, enforcer: Enforcer, lab_port: int,
                 node_a_url: str, probe_period: float = 1.0, autonomous_lab: bool = False):
        self.autonomous_lab = autonomous_lab
        self.autonomous_used = set()
        self.node_id = node_id
        self.verifier = verifier
        self.enforcer = enforcer
        self.lab_port = lab_port
        self.node_a_url = node_a_url.rstrip("/")
        self.probe_period = probe_period
        self.lock = threading.RLock()
        self._stop = threading.Event()

        self.counts = {
            "alerts_received": 0,
            "alerts_accepted": 0,
            "alerts_rejected": 0,
            "reject_reasons": {},
            "policy": {"PENDING_APPROVAL": 0, "BLOCK": 0, "ALREADY_BLOCKED": 0, "REJECT": 0},
        }
        self.verified_store = {}          # event_id -> (msg, verified)
        self.pending = {}                 # event_id -> summary dict
        self.alert_log = deque(maxlen=80)
        self.enforcer_events = deque(maxlen=60)
        self.probe_history = deque(maxlen=40)
        self.probe_summary = {
            "lab_before": None,
            "lab_during": None,
            "lab_after": None,
            "latest_lab": None,
            "latest_control": None,
        }

        if self.enforcer.startup_cleared:
            self.enforcer_events.appendleft({
                "ts": time.time(),
                "type": "startup_cleanup",
                "targets": self.enforcer.startup_cleared,
                "reason": "cleared leftover journal from previous run",
            })

        self.enforcer.on_event = self._on_enforcer_event
        self._probe_thread = None
        self._node_a_cache = {"reachable": False, "url": self.node_a_url, "status": "connecting"}
        self._node_a_thread = None

    def _on_enforcer_event(self, ev: dict):
        rec = {"ts": time.time(), **ev}
        with self.lock:
            self.enforcer_events.appendleft(rec)
            if ev.get("type") == "block_applied":
                self.probe_summary["lab_during"] = None
                self.probe_summary["lab_after"] = None
                if self.probe_summary["latest_lab"] and self.probe_summary["latest_lab"]["ok"]:
                    self.probe_summary["lab_before"] = self.probe_summary["latest_lab"]

    def start_prober(self):
        self._stop.clear()
        if self.probe_period > 0:
            def loop():
                self.run_probes_once()
                while not self._stop.wait(self.probe_period):
                    self.run_probes_once()

            self._probe_thread = threading.Thread(target=loop, daemon=True, name="lab-prober")
            self._probe_thread.start()

        def poll_node_a():
            while not self._stop.is_set():
                snap = self._fetch_node_a()
                with self.lock:
                    self._node_a_cache = snap
                self._stop.wait(0.4)

        self._node_a_thread = threading.Thread(target=poll_node_a, daemon=True, name="node-a-poller")
        self._node_a_thread.start()

    def stop_prober(self):
        self._stop.set()

    def run_probes_once(self) -> dict:
        lab_blocked_now = self.enforcer.is_blocked(config.LAB_CLIENT)
        lab_res = http_probe(config.LAB_CLIENT, config.HOST, self.lab_port)
        ctrl_res = http_probe(config.CONTROL_CLIENT, config.HOST, self.lab_port)
        lab_res["block_expected"] = lab_blocked_now
        ctrl_res["block_expected"] = False
        with self.lock:
            self.probe_history.appendleft({"ts": lab_res["ts"], "lab": lab_res, "control": ctrl_res})
            self.probe_summary["latest_lab"] = lab_res
            self.probe_summary["latest_control"] = ctrl_res
            if not lab_blocked_now and lab_res["ok"] and self.probe_summary["lab_during"] is None:
                self.probe_summary["lab_before"] = lab_res
            elif lab_blocked_now and not lab_res["ok"]:
                self.probe_summary["lab_during"] = lab_res
            elif not lab_blocked_now and lab_res["ok"] and self.probe_summary["lab_during"] is not None:
                self.probe_summary["lab_after"] = lab_res
        return {"lab": lab_res, "control": ctrl_res}

    def ingest_alert(self, msg) -> tuple[int, dict]:
        now_ts = time.time()
        with self.lock:
            self.counts["alerts_received"] += 1

        try:
            verified = self.verifier.verify(msg)
        except Rejected as rej:
            safe_sub = ""
            safe_id = ""
            safe_seq = None
            safe_node = ""
            if isinstance(msg, dict):
                ea = msg.get("enforcement_action")
                if isinstance(ea, dict):
                    safe_sub = str(ea.get("src_cidr", "")).split("/")[0][:40]
                safe_id = str(msg.get("event_id", ""))[:40]
                safe_seq = msg.get("monotonic_seq") if isinstance(msg.get("monotonic_seq"), int) else None
                safe_node = str(msg.get("node_id", ""))[:64]
            with self.lock:
                self.counts["alerts_rejected"] += 1
                rr = self.counts["reject_reasons"]
                rr[rej.code] = rr.get(rej.code, 0) + 1
                self.alert_log.appendleft({
                    "ts": now_ts,
                    "event_id": safe_id,
                    "seq": safe_seq,
                    "node_id": safe_node,
                    "subject": safe_sub,
                    "verification": "rejected",
                    "reject_code": rej.code,
                    "reject_detail": rej.detail,
                    "policy_action": "NONE",
                    "policy_reason": f"Verification failed ({rej.code})",
                    "approval_mode": "none",
                    "target": None,
                })
            status = 403 if rej.code in ("unknown_sender", "bad_signature", "not_authorized") else 400
            return status, {"accepted": False, "code": rej.code, "detail": rej.detail}

        dec = policy.decide(msg, verified, operator_approved=False, is_blocked=self.enforcer.is_blocked)
        subject = msg["enforcement_action"]["src_cidr"].split("/")[0]
        entry = {
            "ts": now_ts,
            "event_id": msg["event_id"],
            "seq": msg["monotonic_seq"],
            "node_id": msg["node_id"],
            "sender_name": verified["sender_name"],
            "subject": subject,
            "risk": msg["detection"]["risk"],
            "threshold_r_block": msg["detection"]["threshold_r_block"],
            "surprise_ewma": msg["detection"]["surprise_ewma"],
            "hazard_ewma": msg["detection"]["hazard_ewma"],
            "recorded_offset_s": msg["detection"]["recorded_offset_s"],
            "input_mode": msg["detection"]["input_mode"],
            "stage": msg["ncm_prediction"]["kill_chain_phase"],
            "verification": "accepted",
            "reject_code": None,
            "reject_detail": None,
            "policy_action": dec.action,
            "policy_reason": dec.reason,
            "approval_mode": dec.approval_mode,
            "target": dec.target,
            "ttl_seconds": dec.ttl_seconds,
            "scope": dec.scope,
        }
        with self.lock:
            self.counts["alerts_accepted"] += 1
            self.counts["policy"][dec.action] = self.counts["policy"].get(dec.action, 0) + 1
            self.verified_store[msg["event_id"]] = (msg, verified)
            if dec.action == "PENDING_APPROVAL":
                # Keep one active pending approval per target (supersede older unapproved ones for the same target)
                for p in self.pending.values():
                    if p["target"] == dec.target and p["status"] == "pending":
                        p["status"] = "superseded"
                self.pending[msg["event_id"]] = {**entry, "status": "pending"}
            self.alert_log.appendleft(entry)
            if dec.action == "PENDING_APPROVAL" and self.autonomous_lab:
                previous_action = dec.action
                dec = self._autonomous_attempt(msg, verified, dec)
                self.counts["policy"][previous_action] -= 1
                self.counts["policy"][dec.action] += 1
                entry["policy_action"] = dec.action
                entry["policy_reason"] = dec.reason
                entry["approval_mode"] = dec.approval_mode
                if dec.action == "BLOCK":
                    entry["ttl_seconds"] = dec.ttl_seconds

        return 200, {
            "accepted": True,
            "event_id": msg["event_id"],
            "policy_action": dec.action,
            "reason": dec.reason,
            "target": dec.target,
            "approval_mode": dec.approval_mode,
        }

    def _autonomous_attempt(self, msg, verified, decision):
        """Called under the state lock; recorded replay may gate one lab client once."""
        target = decision.target
        pending = self.pending[msg["event_id"]]
        if (target != config.LAB_CLIENT or msg["detection"]["input_mode"] != "recorded-replay"
                or not verified.get("expected_model_onnx_sha256")):
            return decision
        if self.enforcer.is_blocked(target):
            pending["status"] = "already_blocked"
            return policy.Decision("ALREADY_BLOCKED", "existing block is not extended", target)
        if target in self.autonomous_used:
            pending["status"] = "autonomous_budget_exhausted"
            return policy.Decision("REJECT", "automatic lab budget exhausted; restart with explicit opt-in for another run")
        if msg["expires_ns"] <= time.time_ns():
            pending["status"] = "expired"
            return policy.Decision("REJECT", "alert expired before automatic action")
        # Reserve the one-shot allowance before calling enforcement, including on failure.
        self.autonomous_used.add(target)
        pending["status"] = "autonomous_consumed"
        ttl = min(decision.ttl_seconds, config.AUTONOMOUS_BLOCK_SECONDS)
        result = self.enforcer.block(target, ttl, event_id=msg["event_id"],
            approval_mode="autonomous-lab", reason="explicit lab opt-in; recorded alert, no independent local sensing")
        if not result.get("ok"):
            return policy.Decision("REJECT", result.get("error", "lab enforcement failed"))
        return policy.Decision("BLOCK", "one-shot autonomous lab block; not G1-approved", target, ttl,
                               "autonomous-lab", decision.scope)

    def disable_autonomy(self):
        with self.lock:
            self.autonomous_lab = False
            result = self._unblock_target_locked(None)
            return {"ok": True, "autonomous_lab": False, **result}

    def approve_event(self, event_id: str) -> tuple[int, dict]:
        # Serialize approval with ingestion/supersession. Enforcer callbacks reenter this lock.
        with self.lock:
            return self._approve_event_locked(event_id)

    def _approve_event_locked(self, event_id: str) -> tuple[int, dict]:
        with self.lock:
            stored = self.verified_store.get(event_id)
        if stored is None:
            return 404, {"ok": False, "error": "verified event_id not found"}
        msg, verified = stored
        pending = self.pending.get(event_id)
        if pending is None:
            return 409, {"ok": False, "error": "event is not pending approval"}
        now = time.time_ns()
        if msg["expires_ns"] <= now or msg["timestamp_ns"] > now + config.CLOCK_SKEW_S * 1e9:
            pending["status"] = "expired"
            return 409, {"ok": False, "error": "event is no longer fresh"}
        if pending["status"] == "approved":
            active = any(b["event_id"] == event_id for b in self.enforcer.active())
            if active:
                return 200, {"ok": True, "already": True, "action": "ALREADY_BLOCKED",
                             "target": pending["target"], "probes": self.run_probes_once()}
        if pending["status"] != "pending":
            return 409, {"ok": False, "error": "event already consumed or superseded"}
        dec = policy.decide(msg, verified, operator_approved=True, is_blocked=self.enforcer.is_blocked)
        if dec.action == "REJECT":
            return 403, {"ok": False, "action": dec.action, "reason": dec.reason}
        if dec.action == "ALREADY_BLOCKED":
            with self.lock:
                if event_id in self.pending:
                    self.pending[event_id]["status"] = "already_blocked"
            probes = self.run_probes_once()
            return 200, {"ok": True, "already": True, "action": dec.action, "reason": dec.reason,
                         "target": dec.target, "probes": probes}

        res = self.enforcer.block(
            dec.target,
            dec.ttl_seconds,
            event_id=event_id,
            approval_mode=dec.approval_mode,
            reason=dec.reason,
        )
        if not res.get("ok"):
            return 403, res
        with self.lock:
            if event_id in self.pending:
                self.pending[event_id]["status"] = "approved"
            for p in self.pending.values():
                if p["target"] == dec.target and p["status"] == "pending":
                    p["status"] = "superseded"
        probes = self.run_probes_once()
        return 200, {"ok": True, "already": bool(res.get("already")), "action": "BLOCK",
                     "approval_mode": dec.approval_mode, "block": res, "probes": probes}

    def unblock_target(self, target: str | None = None) -> dict:
        with self.lock:
            return self._unblock_target_locked(target)

    def _unblock_target_locked(self, target: str | None = None) -> dict:
        removed = self.enforcer.unblock(target, why="manual")
        with self.lock:
            for p in self.pending.values():
                if p["status"] == "pending" and (target is None or p["target"] == target):
                    p["status"] = "cleared"
        probes = self.run_probes_once()
        return {"ok": True, "removed": removed, "probes": probes}

    def _fetch_node_a(self) -> dict:
        try:
            with urllib.request.urlopen(f"{self.node_a_url}/status", timeout=0.5) as resp:
                data = json.loads(resp.read().decode())
                return {"reachable": True, **data}
        except Exception as e:
            return {"reachable": False, "url": self.node_a_url, "error": str(e)}

    def snapshot(self) -> dict:
        active_blocks = self.enforcer.active()
        with self.lock:
            node_a = json.loads(json.dumps(self._node_a_cache))
            pending_active = [p for p in reversed(list(self.pending.values())) if p["status"] == "pending"]
            return {
                "ts": time.time(),
                "sandbox": config.SANDBOX,
                "simulated_notice": (
                    "Two-node cooperative prototype on 127.0.0.1. "
                    "Not decentralized consensus, federated learning, or production enforcement."
                ),
                "node_a": node_a,
                "node_b": {
                    "node": "Node B (simulated site-b)",
                    "autonomous_lab": self.autonomous_lab,
                    "autonomous_targets_used": sorted(self.autonomous_used),
                    "automatic_block_seconds": config.AUTONOMOUS_BLOCK_SECONDS,
                    "autonomy_notice": "Lab automation only; recorded traffic mapped to loopback. No independent sensing or G1 approval.",
                    "node_id": self.node_id,
                    "listen": f"{config.HOST}:{config.NODE_B_PORT}",
                    "lab_service": f"http://{config.HOST}:{self.lab_port}/",
                    "lab_client_allowlist": sorted(config.LAB_CLIENT_ALLOWLIST),
                    "protected_addresses": sorted(config.PROTECTED_ADDRESSES),
                    "subject_map": dict(config.SUBJECT_MAP),
                    "max_block_seconds": config.MAX_BLOCK_SECONDS,
                    "trusted_senders": list(self.verifier.trust.keys()),
                    "counts": json.loads(json.dumps(self.counts)),
                    "pending_approvals": pending_active,
                    "active_blocks": active_blocks,
                    "drops_total": self.enforcer.total_drops(),
                    "drops_by_ip": self.enforcer.drops_by_ip(),
                    "startup_cleared": self.enforcer.startup_cleared,
                    "alert_log": list(self.alert_log)[:30],
                    "enforcer_events": list(self.enforcer_events)[:20],
                    "probe_summary": json.loads(json.dumps(self.probe_summary)),
                    "probe_history": list(self.probe_history)[:15],
                },
            }


def make_handler(state: NodeBState, dashboard_path: Path):
    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, code: int, payload: dict):
            raw = json.dumps(payload).encode()
            try:
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                pass

        def _send_html(self, path: Path):
            raw = path.read_bytes()
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                pass

        def _require_operator(self) -> bool:
            if self.headers.get(config.OPERATOR_HEADER) != "1":
                self._send_json(403, {"ok": False, "error": f"missing {config.OPERATOR_HEADER} header"})
                return False
            return True

        def _read_json(self):
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length > 262144:
                return None, "payload too large"
            raw = self.rfile.read(length) if length else b"{}"
            try:
                return json.loads(raw.decode() or "{}"), None
            except ValueError:
                return None, "invalid json"

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in ("/", "/index.html", "/dashboard.html"):
                self._send_html(dashboard_path)
            elif path == "/health":
                self._send_json(200, {"ok": True})
            elif path == "/recorded_fallback.json":
                fb = dashboard_path.parent / "recorded_fallback.json"
                if fb.is_file():
                    raw = fb.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                else:
                    self._send_json(404, {"error": "recorded_fallback.json not found"})
            elif path == "/api/state":
                self._send_json(200, state.snapshot())
            elif path in ("/api/report", "/api/report.md"):
                # Read-only, rule-based summary of the structured state (see report.py); decides nothing.
                rep = report.build_report(state.snapshot())
                if path.endswith(".md"):
                    raw = rep["markdown"].encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/markdown; charset=utf-8")
                    self.send_header("Content-Disposition", 'attachment; filename="cyberncm-demo-report.md"')
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                else:
                    self._send_json(200, rep)
            else:
                self._send_json(404, {"error": "not found"})

        def do_POST(self):
            path = self.path.split("?")[0]
            if path == "/api/alerts":
                body, err = self._read_json()
                if err:
                    code, resp = state.ingest_alert(body if body is not None else err)
                    self._send_json(code, resp)
                    return
                code, resp = state.ingest_alert(body)
                self._send_json(code, resp)
                return

            if not self._require_operator():
                return

            body, err = self._read_json()
            if err:
                self._send_json(400, {"ok": False, "error": err})
                return

            if path == "/api/autonomy/disable":
                self._send_json(200, state.disable_autonomy())
            elif path == "/api/approve":
                event_id = str(body.get("event_id", ""))
                code, resp = state.approve_event(event_id)
                self._send_json(code, resp)
            elif path == "/api/unblock":
                target = body.get("target")
                self._send_json(200, state.unblock_target(target))
            elif path == "/api/probe":
                self._send_json(200, {"ok": True, "probes": state.run_probes_once()})
            elif path in ("/api/node-a/start", "/api/node-a/pause", "/api/node-a/reset", "/api/node-a/speed"):
                sub = path.replace("/api/node-a/", "/replay/")
                req = urllib.request.Request(
                    f"{state.node_a_url}{sub}",
                    data=json.dumps(body).encode(),
                    headers={"Content-Type": "application/json", config.OPERATOR_HEADER: "1"},
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(req, timeout=2.0) as resp:
                        self._send_json(resp.status, json.loads(resp.read().decode()))
                except urllib.error.HTTPError as e:
                    self._send_json(e.code, json.loads(e.read().decode() or "{}"))
                except Exception as e:
                    self._send_json(502, {"ok": False, "error": f"Node A unreachable: {e}"})
            else:
                self._send_json(404, {"error": "not found"})

        def log_message(self, *a):
            pass

    return Handler


class NodeBServer(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True


def build_node_b(*, port: int = config.NODE_B_PORT, lab_port: int = config.LAB_PORT,
                 node_a_url: str = f"http://{config.HOST}:{config.NODE_A_PORT}",
                 runtime_dir: Path = config.RUNTIME, probe_period: float = 1.0,
                 autonomous_lab: bool = config.AUTONOMOUS_LAB):
    info = ensure_setup(runtime_dir=runtime_dir)
    trust = load_trust(runtime_dir / "trusted_senders.json")
    verifier = Verifier(trust, runtime_dir / "state" / "verifier_state.json", lab_port=lab_port)
    enforcer = Enforcer(runtime_dir / "state" / "enforcer_journal.json", lab_port=lab_port)
    enforcer.start_reaper(0.25)
    gate = LabGate(enforcer, config.HOST, lab_port)
    threading.Thread(target=gate.serve_forever, daemon=True, name="lab-gate").start()

    state = NodeBState(
        node_id=info["node_b_id"],
        verifier=verifier,
        enforcer=enforcer,
        lab_port=lab_port,
        node_a_url=node_a_url,
        probe_period=probe_period,
        autonomous_lab=autonomous_lab,
    )
    state.start_prober()
    dashboard_path = Path(__file__).resolve().parent / "dashboard.html"
    srv = NodeBServer((config.HOST, port), make_handler(state, dashboard_path))

    def cleanup():
        state.stop_prober()
        enforcer.unblock(None, why="shutdown")
        enforcer.stop_reaper()
        try:
            gate.shutdown()
            gate.server_close()
        except Exception:
            pass
        try:
            srv.server_close()
        except Exception:
            pass

    return srv, gate, state, cleanup


def main():
    ap = argparse.ArgumentParser(description="CyberNCM two-node demo: Node B (verifier, policy, enforcer, dashboard).")
    ap.add_argument("--port", type=int, default=config.NODE_B_PORT)
    ap.add_argument("--lab-port", type=int, default=config.LAB_PORT)
    ap.add_argument("--node-a", default=f"http://{config.HOST}:{config.NODE_A_PORT}")
    args = ap.parse_args()

    srv, gate, state, cleanup = build_node_b(port=args.port, lab_port=args.lab_port, node_a_url=args.node_a)
    atexit.register(cleanup)

    def handle_sig(*_):
        threading.Thread(target=srv.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    print(
        f"Node B ({state.node_id[:40]}...) dashboard http://{config.HOST}:{args.port}/  |  "
        f"Lab HTTP gate http://{config.HOST}:{args.lab_port}/",
        flush=True,
    )
    try:
        srv.serve_forever()
    finally:
        cleanup()


if __name__ == "__main__":
    main()
