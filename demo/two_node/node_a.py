"""Simulated Site A (Node A): frozen FP32 ONNX detector + signed NCMThreatDirective sender.

Reads recorded CIC-IDS2017 Friday windows (read-only), warms up from day start through the FP32
ONNX model so hidden state and EWMA match ncm/stream.py, then streams a replay segment at
configurable speed and POSTs signed v1.2.0 directives to Node B.

Model weights, normalization, codebooks, and thresholds are frozen: zero learning from incoming data.
"""
import argparse
import ipaddress
import json
import signal
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch

import config
from bootstrap import ensure_setup, model_metadata
from protocol import Sender, load_or_create_key

sys.path.insert(0, str(config.REPO / "ncm"))
from ncm import EWMA, STAGES  # noqa: E402


class ReplayEngine:
    """Thread-safe FP32 ONNX replay engine + signed alert sender."""

    def __init__(self, sender: Sender, node_b_url: str, checkpoint_path: Path = config.CHECKPOINT,
                 windows_path: Path = config.WINDOWS, speed: float = config.REPLAY_SPEED):
        self.sender = sender
        self.node_b_url = node_b_url.rstrip("/")
        self.speed = float(speed)
        self.lock = threading.Lock()
        self._stop = threading.Event()
        self._run_flag = threading.Event()

        self.meta = model_metadata(checkpoint_path, windows_path)
        ck = torch.load(checkpoint_path, map_location="cpu")
        self.thr = {k: float(v) for k, v in ck["thresholds"].items()}

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        self.sess = ort.InferenceSession(self.meta["onnx_path"], opts)
        self.layers = self.sess.get_inputs()[1].shape[0]
        self.hdim = self.sess.get_inputs()[1].shape[2]

        z = np.load(windows_path)
        m = z["day"] == config.REPLAY_DAY
        self.X = z["X"][m]
        self.src = z["src"][m]
        self.t = z["t"][m]
        self.fam = z["family"][m]
        self.names = [str(x) for x in z["family_names"]]
        self.ips, self.sid = np.unique(self.src, return_inverse=True)
        self.n_src = len(self.ips)
        self.t0 = float(self.t.min())
        self.times = np.unique(self.t)

        # Warm up identically to ncm/stream.py up to REPLAY_START so H, EWMA, and cooldowns match
        self.status = "warming_up"
        self._H_warm = np.zeros((self.layers, self.n_src, self.hdim), np.float32)
        self._s_warm = np.full(self.n_src, np.nan)
        self._h_warm = np.full(self.n_src, np.nan)
        self._until_warm = np.zeros(self.n_src)
        self.start_idx = 0
        self.end_idx = len(self.times)
        for idx, now in enumerate(self.times):
            off = float(now - self.t0)
            if off >= config.REPLAY_START:
                self.start_idx = idx
                break
            rows = np.flatnonzero(self.t == now)
            i = self.sid[rows]
            sup, probs, _, _, h_out = self.sess.run(None, {"x": self.X[rows], "h": self._H_warm[:, i]})
            self._H_warm[:, i] = h_out
            hz = 1.0 - probs[:, 0]
            self._s_warm[i] = np.where(np.isnan(self._s_warm[i]), sup, EWMA * sup + (1.0 - EWMA) * self._s_warm[i])
            self._h_warm[i] = np.where(np.isnan(self._h_warm[i]), hz, EWMA * hz + (1.0 - EWMA) * self._h_warm[i])
            risk = 0.5 * np.clip((self._s_warm[i] - self.thr["q50"]) / (self.thr["q999"] - self.thr["q50"]), 0.0, 1.0) + 0.5 * self._h_warm[i]
            for j in np.flatnonzero(risk > self.thr["r_block"]):
                s = i[j]
                if self._until_warm[s] <= now:
                    ip = ipaddress.ip_address(int(self.ips[s]))
                    if not any(ip in net for net in config.PROTECTED_RECORDED):
                        self._until_warm[s] = now + config.MAX_BLOCK_SECONDS

        for idx in range(self.start_idx, len(self.times)):
            if float(self.times[idx] - self.t0) > config.REPLAY_START + config.REPLAY_DURATION:
                self.end_idx = idx
                break

        self._reset_locked()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="node-a-replay")
        self._thread.start()

    def _reset_locked(self):
        self.H = self._H_warm.copy()
        self.s_avg = self._s_warm.copy()
        self.h_avg = self._h_warm.copy()
        self.until = self._until_warm.copy()
        self.cur_idx = self.start_idx
        self.cur_offset_s = float(self.times[self.start_idx] - self.t0) if self.start_idx < self.end_idx else float(config.REPLAY_START)
        self.windows_scored = 0
        self.alerts_sent_count = 0
        self.node_b_accepted = 0
        self.node_b_rejected = 0
        self.node_b_errors = 0
        self.node_b_state = "idle"
        self.last_score = None
        self.recent_windows = deque(maxlen=15)
        self.recent_alerts = deque(maxlen=25)
        self.status = "ready"

    def start(self):
        with self.lock:
            if self.status == "finished":
                self._reset_locked()
            self.status = "replaying"
        self._run_flag.set()

    def pause(self):
        self._run_flag.clear()
        with self.lock:
            if self.status == "replaying":
                self.status = "paused"

    def reset(self, autostart: bool = False):
        self._run_flag.clear()
        with self.lock:
            self._reset_locked()
            if autostart:
                self.status = "replaying"
        if autostart:
            self._run_flag.set()

    def set_speed(self, speed: float):
        if speed not in (1.0, 5.0, 10.0, 20.0):
            raise ValueError("speed must be 1, 5, 10, or 20")
        with self.lock:
            self.speed = float(speed)

    def stop(self):
        self._stop.set()
        self._run_flag.set()

    def _post_alert(self, directive: dict) -> dict:
        body = json.dumps(directive).encode()
        req = urllib.request.Request(
            f"{self.node_b_url}/api/alerts",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode())
                return {"reachable": True, "http_status": resp.status, **data}
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors="replace")
            try:
                data = json.loads(raw)
            except ValueError:
                data = {"detail": raw}
            return {"reachable": True, "http_status": e.code, **data}
        except Exception as e:
            return {"reachable": False, "http_status": None, "accepted": False, "error": str(e)}

    def _step_once(self) -> bool:
        with self.lock:
            if not self._run_flag.is_set() or self.cur_idx >= self.end_idx:
                if self.cur_idx >= self.end_idx and self.status == "replaying":
                    self.status = "finished"
                    self._run_flag.clear()
                return False
            idx = self.cur_idx
            now = float(self.times[idx])
            off = float(now - self.t0)
            rows = np.flatnonzero(self.t == now)
            i = self.sid[rows]
            sup, probs, tok, nxt, h_out = self.sess.run(None, {"x": self.X[rows], "h": self.H[:, i]})
            self.H[:, i] = h_out
            hz = 1.0 - probs[:, 0]
            self.s_avg[i] = np.where(np.isnan(self.s_avg[i]), sup, EWMA * sup + (1.0 - EWMA) * self.s_avg[i])
            self.h_avg[i] = np.where(np.isnan(self.h_avg[i]), hz, EWMA * hz + (1.0 - EWMA) * self.h_avg[i])
            risk = 0.5 * np.clip((self.s_avg[i] - self.thr["q50"]) / (self.thr["q999"] - self.thr["q50"]), 0.0, 1.0) + 0.5 * self.h_avg[i]

            # Record telemetry for display (ground truth stored separately from detector output)
            best_j = int(np.argmax(risk))
            for j in range(len(rows)):
                ip_str = str(ipaddress.ip_address(int(self.ips[i[j]])))
                if ip_str in config.SUBJECT_MAP:
                    best_j = j
                    break
            chosen_s = i[best_j]
            chosen_ip = str(ipaddress.ip_address(int(self.ips[chosen_s])))
            chosen_stage = STAGES[1 + int(probs[best_j, 1:].argmax())]
            step_rec = {
                "recorded_offset_s": round(off, 1),
                "batch_sources": len(rows),
                "subject": chosen_ip,
                "risk": round(float(risk[best_j]), 4),
                "threshold_r_block": round(self.thr["r_block"], 4),
                "threshold_r_limit": round(self.thr["r_limit"], 4),
                "surprise_ewma": round(float(self.s_avg[chosen_s]), 3),
                "hazard_ewma": round(float(self.h_avg[chosen_s]), 4),
                "inferred_stage": chosen_stage,
                "dataset_ground_truth_only": self.names[int(self.fam[rows[best_j]])],
                "above_quarantine_threshold": bool(risk[best_j] > self.thr["r_block"]),
            }
            self.last_score = step_rec
            self.recent_windows.appendleft(step_rec)
            self.windows_scored += len(rows)
            self.cur_offset_s = off
            self.cur_idx += 1

            to_send = []
            for j in np.flatnonzero(risk > self.thr["r_block"]):
                s = i[j]
                if self.until[s] > now:
                    continue
                ip = ipaddress.ip_address(int(self.ips[s]))
                if any(ip in net for net in config.PROTECTED_RECORDED):
                    continue
                self.until[s] = now + config.MAX_BLOCK_SECONDS
                stage = STAGES[1 + int(probs[j, 1:].argmax())]
                dct = self.sender.build(
                    subject_ip=str(ip),
                    kill_chain_phase=stage,
                    surprise=float(self.s_avg[s]),
                    hazard=float(self.h_avg[s]),
                    token=int(tok[j]),
                    next_token=int(nxt[j]),
                    model={
                        "format": "onnx-fp32",
                        "onnx_sha256": self.meta["onnx_sha256"],
                        "checkpoint_sha256": self.meta["checkpoint_sha256"],
                    },
                    detection={
                        "input_mode": "recorded-replay",
                        "windows_sha256": self.meta["windows_sha256"],
                        "recorded_offset_s": round(off, 1),
                        "risk": float(risk[j]),
                        "threshold_r_block": self.thr["r_block"],
                        "surprise_ewma": float(self.s_avg[s]),
                        "hazard_ewma": float(self.h_avg[s]),
                    },
                    ttl_seconds=config.MAX_BLOCK_SECONDS,
                )
                to_send.append((dct, self.names[int(self.fam[rows[j]])]))

        # Network sends happen outside the engine lock so status polling stays instant
        for dct, truth in to_send:
            res = self._post_alert(dct)
            with self.lock:
                self.alerts_sent_count += 1
                if not res.get("reachable", False):
                    self.node_b_errors += 1
                    self.node_b_state = "unreachable"
                else:
                    self.node_b_state = "connected"
                    if res.get("accepted"):
                        self.node_b_accepted += 1
                    else:
                        self.node_b_rejected += 1
                self.recent_alerts.appendleft({
                    "event_id": dct["event_id"],
                    "seq": dct["monotonic_seq"],
                    "subject": dct["enforcement_action"]["src_cidr"].split("/")[0],
                    "risk": dct["detection"]["risk"],
                    "threshold_r_block": dct["detection"]["threshold_r_block"],
                    "stage": dct["ncm_prediction"]["kill_chain_phase"],
                    "recorded_offset_s": dct["detection"]["recorded_offset_s"],
                    "dataset_ground_truth_only": truth,
                    "sent_ts": time.time(),
                    "node_b_response": res,
                })
        return True

    def _loop(self):
        while not self._stop.is_set():
            if not self._run_flag.wait(0.1):
                continue
            if self._stop.is_set():
                break
            ran = self._step_once()
            if not ran:
                time.sleep(0.05)
                continue
            with self.lock:
                delay = 5.0 / self.speed
            # Sleep in tiny slices so pause/reset/stop responds immediately
            deadline = time.perf_counter() + delay
            while not self._stop.is_set() and self._run_flag.is_set():
                rem = deadline - time.perf_counter()
                if rem <= 0:
                    break
                time.sleep(min(0.05, rem))

    def snapshot(self) -> dict:
        with self.lock:
            total_steps = max(1, self.end_idx - self.start_idx)
            done_steps = max(0, self.cur_idx - self.start_idx)
            return {
                "node": "Node A (simulated site-a)",
                "node_id": self.sender.node_id,
                "listen": f"{config.HOST}:{config.NODE_A_PORT}",
                "status": self.status,
                "input_mode": "recorded-replay",
                "sandbox": config.SANDBOX,
                "dataset_notice": (
                    "SANDBOX: replaying synthetic windows through a toy model; no real data. "
                    "The detector does NOT inspect live lab-client traffic."
                    if config.SANDBOX else
                    "Replaying recorded CIC-IDS2017 Friday windows. "
                    "The detector does NOT inspect live lab-client traffic."
                ),
                "model": {
                    "format": self.meta["format"],
                    "onnx_sha256": self.meta["onnx_sha256"],
                    "checkpoint_sha256": self.meta["checkpoint_sha256"],
                    "windows_sha256": self.meta["windows_sha256"],
                },
                "thresholds": self.thr,
                "replay": {
                    "day": "synthetic sandbox day" if config.SANDBOX else "Friday (CIC-IDS2017)",
                    "start_offset_s": config.REPLAY_START,
                    "end_offset_s": config.REPLAY_START + config.REPLAY_DURATION,
                    "current_offset_s": round(self.cur_offset_s, 1),
                    "step": done_steps,
                    "total_steps": total_steps,
                    "speed": self.speed,
                    "windows_scored": self.windows_scored,
                },
                "link_to_node_b": {
                    "url": self.node_b_url,
                    "state": self.node_b_state,
                    "alerts_sent": self.alerts_sent_count,
                    "node_b_accepted": self.node_b_accepted,
                    "node_b_rejected": self.node_b_rejected,
                    "transport_errors": self.node_b_errors,
                },
                "last_score": self.last_score,
                "recent_windows": list(self.recent_windows),
                "recent_alerts": list(self.recent_alerts),
            }


def make_handler(engine: ReplayEngine):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, payload: dict):
            raw = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path == "/status":
                self._send(200, engine.snapshot())
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            # Same operator-header rule as Node B: a web page cannot add a custom header cross-origin.
            if self.headers.get(config.OPERATOR_HEADER) != "1":
                self._send(403, {"ok": False, "error": f"missing {config.OPERATOR_HEADER} header"})
                return
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(min(length, 65536)) if length else b"{}"
            try:
                body = json.loads(raw.decode() or "{}")
            except ValueError:
                self._send(400, {"error": "invalid json"})
                return
            if self.path == "/replay/start":
                engine.start()
                self._send(200, {"ok": True, "status": "replaying"})
            elif self.path == "/replay/pause":
                engine.pause()
                self._send(200, {"ok": True, "status": "paused"})
            elif self.path == "/replay/reset":
                engine.reset(autostart=bool(body.get("autostart", False)))
                self._send(200, {"ok": True, "status": engine.snapshot()["status"]})
            elif self.path == "/replay/speed":
                try:
                    engine.set_speed(float(body.get("speed", 10)))
                    self._send(200, {"ok": True, "speed": engine.snapshot()["replay"]["speed"]})
                except (TypeError, ValueError) as e:
                    self._send(400, {"error": str(e)})
            else:
                self._send(404, {"error": "not found"})

        def log_message(self, *a):
            pass

    return Handler


class NodeAServer(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True


def main():
    ap = argparse.ArgumentParser(description="CyberNCM two-node demo: Node A (detector + sender).")
    ap.add_argument("--port", type=int, default=config.NODE_A_PORT)
    ap.add_argument("--node-b", default=f"http://{config.HOST}:{config.NODE_B_PORT}")
    ap.add_argument("--speed", type=float, default=config.REPLAY_SPEED)
    ap.add_argument("--autostart", action="store_true")
    args = ap.parse_args()

    ensure_setup()
    key = load_or_create_key(config.KEYS / "node_a.key")
    sender = Sender(key, config.STATE / "node_a_seq.json")
    engine = ReplayEngine(sender, args.node_b, speed=args.speed)
    srv = NodeAServer((config.HOST, args.port), make_handler(engine))

    def shutdown(*_):
        engine.stop()
        threading.Thread(target=srv.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    if args.autostart:
        engine.start()

    print(f"Node A ({sender.node_id[:40]}...) listening on http://{config.HOST}:{args.port} -> Node B {args.node_b}", flush=True)
    try:
        srv.serve_forever()
    finally:
        engine.stop()
        srv.server_close()


if __name__ == "__main__":
    main()
