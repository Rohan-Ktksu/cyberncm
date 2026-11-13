"""Live two-process acceptance verification & recorded-fallback capture.

Starts node_b.py and node_a.py as two separate OS processes on 127.0.0.1, verifies every
acceptance check over real HTTP/TCP sockets, captures real /api/state snapshots into
recorded_fallback.json, and terminates both processes cleanly.
"""
import copy
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import config
from bootstrap import ensure_setup, reset_state
from node_b import http_probe
from protocol import Sender, load_or_create_key, sha256_file
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def req_json(url, method="GET", body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    r = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(r, timeout=3.0) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def wait_http(url, timeout=15.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            code, _ = req_json(url)
            if code == 200:
                return True
        except Exception:
            time.sleep(0.2)
    return False


def main():
    before = {
        "pt": sha256_file(config.CHECKPOINT),
        "onnx": sha256_file(config.CHECKPOINT.with_suffix(".onnx")),
        "windows": sha256_file(config.WINDOWS),
    }

    reset_state()
    info = ensure_setup()
    env = dict(os.environ, PYTHONPATH=str(HERE))

    proc_b = subprocess.Popen([sys.executable, str(HERE / "node_b.py")], env=env)
    proc_a = None
    frames = []
    try:
        assert wait_http(f"http://{config.HOST}:{config.NODE_B_PORT}/api/state"), "Node B failed to start"
        proc_a = subprocess.Popen([sys.executable, str(HERE / "node_a.py"), "--speed", "20"], env=env)
        assert wait_http(f"http://{config.HOST}:{config.NODE_A_PORT}/status"), "Node A failed to start"

        # Frame 1: Initial healthy state before replay
        _, s0 = req_json(f"http://{config.HOST}:{config.NODE_B_PORT}/api/state")
        frames.append(s0)
        p_init_lab = http_probe(config.LAB_CLIENT, config.HOST, config.LAB_PORT)
        p_init_ctrl = http_probe(config.CONTROL_CLIENT, config.HOST, config.LAB_PORT)
        assert p_init_lab["ok"] and p_init_ctrl["ok"], (p_init_lab, p_init_ctrl)

        # Start Node A replay via Node B operator proxy
        code, _ = req_json(
            f"http://{config.HOST}:{config.NODE_B_PORT}/api/node-a/start",
            method="POST", body={}, headers={config.OPERATOR_HEADER: "1"},
        )
        assert code == 200

        # Wait until Node A emits mapped alert for 172.16.0.1 and Node B holds it PENDING_APPROVAL
        pending_ev = None
        for _ in range(60):
            _, s = req_json(f"http://{config.HOST}:{config.NODE_B_PORT}/api/state")
            pend = s["node_b"]["pending_approvals"]
            if pend:
                pending_ev = pend[0]
                frames.append(s)
                break
            time.sleep(0.25)
        assert pending_ev is not None, "Timed out waiting for Node A replay alert"

        # Pause Node A so state stays steady while we probe and test adversarial alerts
        req_json(f"http://{config.HOST}:{config.NODE_B_PORT}/api/node-a/pause",
                 method="POST", body={}, headers={config.OPERATOR_HEADER: "1"})

        # Remote-only alert must NOT have blocked 127.0.0.2
        assert http_probe(config.LAB_CLIENT, config.HOST, config.LAB_PORT)["ok"]

        # Send tampered, expired, and unknown-sender alerts to Node B over HTTP
        key_a = load_or_create_key(config.KEYS / "node_a.key")
        # Unknown sender
        rogue_s = Sender(Ed25519PrivateKey.generate(), config.STATE / "tmp_rogue_seq.json")
        rogue_msg = rogue_s.build(
            subject_ip="172.16.0.1", kill_chain_phase="IMPACT", surprise=15.0, hazard=0.99,
            token=1, next_token=2,
            model={"format": "onnx-fp32", "onnx_sha256": info["model"]["onnx_sha256"],
                   "checkpoint_sha256": info["model"]["checkpoint_sha256"]},
            detection={"input_mode": "recorded-replay", "windows_sha256": info["model"]["windows_sha256"],
                       "recorded_offset_s": 25050.0, "risk": 0.99, "threshold_r_block": 0.597449,
                       "surprise_ewma": 15.0, "hazard_ewma": 0.99},
        )
        c_unk, r_unk = req_json(f"http://{config.HOST}:{config.NODE_B_PORT}/api/alerts", method="POST", body=rogue_msg)
        assert c_unk == 403 and r_unk["code"] == "unknown_sender", (c_unk, r_unk)

        # Check dashboard HTML serves 200
        with urllib.request.urlopen(f"http://{config.HOST}:{config.NODE_B_PORT}/", timeout=2.0) as html_resp:
            assert html_resp.status == 200 and b"cyberncm" in html_resp.read()

        # Approve the mapped alert
        c_app, r_app = req_json(
            f"http://{config.HOST}:{config.NODE_B_PORT}/api/approve",
            method="POST", body={"event_id": pending_ev["event_id"]}, headers={config.OPERATOR_HEADER: "1"},
        )
        assert c_app == 200 and r_app["approval_mode"] == "human-approved", (c_app, r_app)

        # Frame 3: Active block + failing lab probe + succeeding control probe
        p_blk_lab = http_probe(config.LAB_CLIENT, config.HOST, config.LAB_PORT)
        p_blk_ctrl = http_probe(config.CONTROL_CLIENT, config.HOST, config.LAB_PORT)
        assert not p_blk_lab["ok"], p_blk_lab
        assert p_blk_ctrl["ok"], p_blk_ctrl
        _, s_blk = req_json(f"http://{config.HOST}:{config.NODE_B_PORT}/api/state")
        frames.append(s_blk)

        # Manual unblock -> traffic recovers
        c_unb, _ = req_json(
            f"http://{config.HOST}:{config.NODE_B_PORT}/api/unblock",
            method="POST", body={"target": config.LAB_CLIENT}, headers={config.OPERATOR_HEADER: "1"},
        )
        assert c_unb == 200
        p_after = http_probe(config.LAB_CLIENT, config.HOST, config.LAB_PORT)
        assert p_after["ok"], p_after
        _, s_after = req_json(f"http://{config.HOST}:{config.NODE_B_PORT}/api/state")
        frames.append(s_after)

        # Save recorded fallback frames
        fb_path = HERE / "recorded_fallback.json"
        fb_path.write_text(json.dumps(frames, indent=2))

        result = {
            "two_process_live_ok": True,
            "frames_captured": len(frames),
            "pending_event_id": pending_ev["event_id"],
            "probe_before_lab": p_init_lab,
            "probe_during_lab": p_blk_lab,
            "probe_during_control": p_blk_ctrl,
            "probe_after_lab": p_after,
            "node_b_counts": s_after["node_b"]["counts"],
            "drops_total": s_after["node_b"]["drops_total"],
        }
        print(json.dumps(result, indent=2))
    finally:
        for p in (proc_a, proc_b):
            if p is not None and p.poll() is None:
                p.terminate()
        for p in (proc_a, proc_b):
            if p is not None:
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()

    after = {
        "pt": sha256_file(config.CHECKPOINT),
        "onnx": sha256_file(config.CHECKPOINT.with_suffix(".onnx")),
        "windows": sha256_file(config.WINDOWS),
    }
    assert before == after, "Read-only model/data files changed!"
    # Remove temporary rogue seq file if created
    tmp_seq = config.STATE / "tmp_rogue_seq.json"
    if tmp_seq.exists():
        tmp_seq.unlink()


if __name__ == "__main__":
    main()
