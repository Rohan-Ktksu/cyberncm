"""One-command launcher for the two-node cooperative demo (two separate OS processes on 127.0.0.1)."""
import argparse
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import config
from bootstrap import ensure_setup, reset_state


def wait_ready(url: str, timeout: float = 15.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


def main():
    ap = argparse.ArgumentParser(description="Start Node B and Node A as separate processes on 127.0.0.1.")
    ap.add_argument("--reset-state", action="store_true", help="Reset sequence numbers, replay cache, and block journal before start.")
    ap.add_argument("--autostart", action="store_true", help="Start Node A replay automatically once warmed up.")
    ap.add_argument("--speed", type=float, default=config.REPLAY_SPEED)
    ap.add_argument("--autonomous-lab", action="store_true", help="Explicitly allow one automatic 10s loopback block per client in this Node B process. Not G1-approved.")
    args = ap.parse_args()

    here = Path(__file__).resolve().parent
    if args.reset_state:
        reset_state()
    info = ensure_setup()
    print(f"Trust configured. Model ONNX SHA-256: {info['model']['onnx_sha256']}")

    env = dict(os.environ)
    env["PYTHONPATH"] = str(here)
    env["CYBERNCM_AUTONOMOUS_LAB"] = "1" if args.autonomous_lab else "0"

    proc_b = subprocess.Popen([sys.executable, str(here / "node_b.py")], env=env)
    if not wait_ready(f"http://{config.HOST}:{config.NODE_B_PORT}/health", timeout=10.0):
        proc_b.terminate()
        raise RuntimeError("Node B did not become ready in time")

    cmd_a = [sys.executable, str(here / "node_a.py"), "--speed", str(args.speed)]
    if args.autostart:
        cmd_a.append("--autostart")
    proc_a = subprocess.Popen(cmd_a, env=env)
    if not wait_ready(f"http://{config.HOST}:{config.NODE_A_PORT}/status", timeout=15.0):
        proc_a.terminate()
        proc_b.terminate()
        raise RuntimeError("Node A did not become ready in time")

    print("Mode: " + ("AUTONOMOUS LAB: one 10s loopback block per target/process; NOT G1-approved" if args.autonomous_lab else "human-approved (default)"))
    print(f"\nDashboard ready: http://{config.HOST}:{config.NODE_B_PORT}/")
    print("Press Ctrl+C to stop both nodes and clean up all active demo blocks.\n", flush=True)

    try:
        while True:
            if proc_b.poll() is not None:
                print(f"Node B exited with code {proc_b.returncode}")
                break
            if proc_a.poll() is not None:
                print(f"Node A exited with code {proc_a.returncode}")
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping Node A and Node B...")
    finally:
        for p in (proc_a, proc_b):
            if p.poll() is None:
                p.terminate()
        for p in (proc_a, proc_b):
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()
