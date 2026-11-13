"""Verification tests for the two-node cooperative demo (acceptance checks 1-12).

Run from demo/two_node:
    python -m unittest test_two_node.py -v
"""
import copy
import json
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import config
import policy
from bootstrap import ensure_setup, model_metadata
from enforcer import Enforcer, LabGate
from node_a import ReplayEngine
from node_b import NodeBState, build_node_b, http_probe
from protocol import Rejected, Sender, Verifier, load_or_create_key, load_trust, node_id_for, pub_raw, sha256_file
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _sample_detection(meta):
    return {
        "input_mode": "recorded-replay",
        "windows_sha256": meta["windows_sha256"],
        "recorded_offset_s": 25050.0,
        "risk": 0.999,
        "threshold_r_block": 0.597449,
        "surprise_ewma": 15.495,
        "hazard_ewma": 0.998,
    }


def _http_json(url, method="GET", body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


class TwoNodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rt = Path(self.tmp.name)
        try:
            self.info = ensure_setup(runtime_dir=self.rt)
        except FileNotFoundError as e:
            self.skipTest(f"model artifacts are not published; build them as described in the README ({e})")
        self.meta = self.info["model"]
        self.key_a = load_or_create_key(self.rt / "keys" / "node_a.key")
        self.sender = Sender(self.key_a, self.rt / "state" / "node_a_seq.json")
        self.trust = load_trust(self.rt / "trusted_senders.json")
        self.verifier = Verifier(self.trust, self.rt / "state" / "verifier_state.json")

    def tearDown(self):
        self.tmp.cleanup()

    def _build_msg(self, subject="172.16.0.1", **kw):
        model = {"format": "onnx-fp32", "onnx_sha256": self.meta["onnx_sha256"],
                 "checkpoint_sha256": self.meta["checkpoint_sha256"]}
        return self.sender.build(
            subject_ip=subject,
            kill_chain_phase="IMPACT",
            surprise=15.495,
            hazard=0.998,
            token=10,
            next_token=12,
            model=model,
            detection=_sample_detection(self.meta),
            **kw,
        )

    # ---- Acceptance checks 3 & 4: signature, schema, tampering, expiry, replay, unknown sender ----
    def test_valid_and_rejected_messages(self):
        msg = self._build_msg()
        v = self.verifier.verify(msg)
        self.assertEqual(v["sender_name"], "site-a-sim")

        # Tampered message fails signature check
        tampered = copy.deepcopy(msg)
        tampered["detection"]["risk"] = 0.1
        with self.assertRaises(Rejected) as ctx:
            self.verifier.verify(tampered)
        self.assertEqual(ctx.exception.code, "bad_signature")

        # Replayed exact message (same event_id) fails replay check
        with self.assertRaises(Rejected) as ctx:
            self.verifier.verify(msg)
        self.assertEqual(ctx.exception.code, "replay")

        # New event_id with stale/reused monotonic_seq fails replay check
        msg2 = self._build_msg()
        # Resign msg2 with seq=1 (already accepted)
        msg2["monotonic_seq"] = 1
        msg2 = self.sender.sign(msg2)
        with self.assertRaises(Rejected) as ctx:
            self.verifier.verify(msg2)
        self.assertEqual(ctx.exception.code, "replay")

        # Expired message fails expiry check
        now_ns = time.time_ns()
        expired = self._build_msg(now_ns=now_ns - 20_000_000_000, lifetime_s=5)
        with self.assertRaises(Rejected) as ctx:
            self.verifier.verify(expired, now_ns=now_ns)
        self.assertEqual(ctx.exception.code, "expired")

        # Unknown sender fails unknown_sender check
        rogue_key = Ed25519PrivateKey.generate()
        rogue_sender = Sender(rogue_key, self.rt / "state" / "rogue_seq.json")
        rogue_msg = rogue_sender.build(
            subject_ip="172.16.0.1", kill_chain_phase="IMPACT", surprise=15.0, hazard=0.99,
            token=1, next_token=2,
            model={"format": "onnx-fp32", "onnx_sha256": self.meta["onnx_sha256"],
                   "checkpoint_sha256": self.meta["checkpoint_sha256"]},
            detection=_sample_detection(self.meta),
        )
        with self.assertRaises(Rejected) as ctx:
            self.verifier.verify(rogue_msg)
        self.assertEqual(ctx.exception.code, "unknown_sender")

    # ---- Acceptance checks 5 & 6: remote-only never auto-blocks; non-allowlisted rejected ----
    def test_policy_safeguards(self):
        msg = self._build_msg(subject="172.16.0.1")
        v = self.verifier.verify(msg)

        # Remote-only alert without operator approval never blocks
        d1 = policy.decide(msg, v, operator_approved=False)
        self.assertEqual(d1.action, "PENDING_APPROVAL")

        # Operator approval yields human-approved block on allowlisted mapped client
        d2 = policy.decide(msg, v, operator_approved=True)
        self.assertEqual(d2.action, "BLOCK")
        self.assertEqual(d2.target, config.LAB_CLIENT)
        self.assertEqual(d2.approval_mode, "human-approved")
        self.assertLessEqual(d2.ttl_seconds, 30)

        # Unmapped / non-allowlisted subjects are rejected even with operator_approved=True
        for bad_ip in ("192.168.10.8", "127.0.0.1", "127.0.0.3", "8.8.8.8"):
            m_bad = self._build_msg(subject=bad_ip)
            v_bad = self.verifier.verify(m_bad)
            d_bad = policy.decide(m_bad, v_bad, operator_approved=True)
            self.assertEqual(d_bad.action, "REJECT")

        # Enforcer refuses non-allowlisted or protected addresses directly
        enf = Enforcer(self.rt / "state" / "j.json")
        for forbidden in ("127.0.0.1", "127.0.0.3", "192.168.10.8", "8.8.8.8", "0.0.0.0"):
            res = enf.block(forbidden, 10, event_id="a" * 32, approval_mode="human-approved", reason="test")
            self.assertFalse(res["ok"])

        # test-injection mode is never acted on by policy
        inj = self._build_msg(subject="172.16.0.1")
        inj["detection"]["input_mode"] = "test-injection"
        inj = self.sender.sign(inj)
        v_inj = self.verifier.verify(inj)
        self.assertEqual(policy.decide(inj, v_inj, operator_approved=True).action, "REJECT")

    def _approval_state(self):
        clock = [time.time()]
        enf = Enforcer(self.rt / "state" / "approval.json", clock=lambda: clock[0])
        state = NodeBState(node_id="review", verifier=self.verifier, enforcer=enf,
                           lab_port=config.LAB_PORT, node_a_url="http://127.0.0.1:18200")
        state.run_probes_once = lambda: {}
        return state, enf, clock

    def test_expired_pending_alert_cannot_be_approved(self):
        state, enf, _ = self._approval_state()
        msg = self._build_msg()
        self.assertEqual(state.ingest_alert(msg)[0], 200)
        with patch("node_b.time.time_ns", return_value=msg["expires_ns"]):
            self.assertEqual(state.approve_event(msg["event_id"])[0], 409)
        self.assertFalse(enf.active())

    def test_consumed_alert_cannot_reblock_after_unblock_or_expiry(self):
        state, enf, clock = self._approval_state()
        for manual in (True, False):
            msg = self._build_msg()
            self.assertEqual(state.ingest_alert(msg)[0], 200)
            self.assertEqual(state.approve_event(msg["event_id"])[0], 200)
            if manual:
                state.unblock_target(config.LAB_CLIENT)
            else:
                clock[0] += 31
            self.assertEqual(state.approve_event(msg["event_id"])[0], 409)
            self.assertFalse(enf.active())

    def test_superseded_alert_cannot_be_approved(self):
        state, enf, _ = self._approval_state()
        older, newer = self._build_msg(), self._build_msg()
        state.ingest_alert(older)
        state.ingest_alert(newer)
        self.assertEqual(state.approve_event(older["event_id"])[0], 409)
        self.assertFalse(enf.active())
        self.assertEqual(state.approve_event(newer["event_id"])[0], 200)

    def test_concurrent_duplicate_approval_creates_one_block(self):
        state, enf, _ = self._approval_state()
        msg = self._build_msg()
        state.ingest_alert(msg)
        with ThreadPoolExecutor(max_workers=8) as pool:
            replies = list(pool.map(lambda _: state.approve_event(msg["event_id"]), range(8)))
        self.assertTrue(all(code == 200 for code, _ in replies))
        self.assertEqual(sum(not body.get("already", False) for _, body in replies), 1)
        self.assertEqual(sum(e["type"] == "block_applied" for e in state.enforcer_events), 1)
        state.unblock_target(config.LAB_CLIENT)
        self.assertEqual(state.approve_event(msg["event_id"])[0], 409)

    def test_autonomous_lab_one_shot_expiry_and_reuse(self):
        state, enf, clock = self._approval_state()
        state.autonomous_lab = True
        msg = self._build_msg()
        code, reply = state.ingest_alert(msg)
        self.assertEqual(code, 200)
        self.assertEqual(reply["policy_action"], "BLOCK")
        self.assertEqual(reply["approval_mode"], "autonomous-lab")
        self.assertLessEqual(enf.active()[0]["ttl"], 10)
        self.assertEqual(state.ingest_alert(msg)[0], 400)  # replay
        self.assertEqual(state.approve_event(msg["event_id"])[0], 409)
        clock[0] += 11
        self.assertFalse(enf.active())
        newer = self._build_msg()
        self.assertEqual(state.ingest_alert(newer)[1]["policy_action"], "REJECT")
        self.assertFalse(enf.active())

    def test_autonomous_lab_safeguards_and_kill_switch(self):
        state, enf, _ = self._approval_state()
        state.autonomous_lab = True
        forbidden = self._build_msg(subject="127.0.0.3")
        self.assertEqual(state.ingest_alert(forbidden)[1]["policy_action"], "REJECT")
        injected = self._build_msg()
        injected["detection"]["input_mode"] = "test-injection"
        self.assertEqual(state.ingest_alert(self.sender.sign(injected))[1]["policy_action"], "REJECT")
        msg = self._build_msg()
        self.assertEqual(state.ingest_alert(msg)[1]["policy_action"], "BLOCK")
        state.disable_autonomy()
        self.assertFalse(enf.active())
        self.assertFalse(state.snapshot()["node_b"]["autonomous_lab"])
        newer = self._build_msg()
        self.assertEqual(state.ingest_alert(newer)[1]["policy_action"], "PENDING_APPROVAL")
        self.assertFalse(enf.active())

    def test_wall_clock_rollback_does_not_extend_block(self):
        wall, elapsed = [1000.0], [10.0]
        enf = Enforcer(self.rt / "state" / "clock.json", clock=lambda: wall[0], duration_clock=lambda: elapsed[0])
        enf.block(config.LAB_CLIENT, 10, event_id="clock", approval_mode="autonomous-lab", reason="test")
        wall[0] -= 3600
        elapsed[0] += 11
        self.assertFalse(enf.is_blocked(config.LAB_CLIENT))
        self.assertFalse(enf.active())
        self.assertEqual(enf.reap(), [config.LAB_CLIENT])

    # ---- Acceptance check 10: startup crash-cleanup clears leftover journal blocks ----
    def test_startup_cleanup_clears_stale_blocks(self):
        journal = self.rt / "state" / "enforcer_journal.json"
        journal.parent.mkdir(parents=True, exist_ok=True)
        journal.write_text(json.dumps({
            "pid": 999999,
            "blocks": {config.LAB_CLIENT: {"target": config.LAB_CLIENT, "expires": time.time() + 999}},
        }))
        enf = Enforcer(journal)
        self.assertEqual(enf.startup_cleared, [config.LAB_CLIENT])
        self.assertFalse(enf.is_blocked(config.LAB_CLIENT))
        self.assertEqual(enf.active(), [])

    # ---- Acceptance checks 1, 2, 7, 8, 9, 10, 11: full two-node live loopback flow + real FP32 ONNX ----
    def test_end_to_end_real_detector_and_enforcement(self):
        before_hashes = {
            "pt": sha256_file(config.CHECKPOINT),
            "onnx": sha256_file(config.CHECKPOINT.with_suffix(".onnx")),
            "windows": sha256_file(config.WINDOWS),
        }

        # Pick free ephemeral loopback ports so tests never collide with a running demo
        import socket
        def free_port():
            with socket.socket() as s:
                s.bind(("127.0.0.1", 0))
                return s.getsockname()[1]

        port_b = free_port()
        port_lab = free_port()
        port_a = free_port()

        srv_b, gate, state_b, cleanup_b = build_node_b(
            port=port_b,
            lab_port=port_lab,
            node_a_url=f"http://127.0.0.1:{port_a}",
            runtime_dir=self.rt,
            probe_period=0.0,  # deterministic explicit probes in test
        )
        threading.Thread(target=srv_b.serve_forever, daemon=True).start()
        try:
            # 1. Client HTTP requests succeed initially
            p0_lab = http_probe(config.LAB_CLIENT, config.HOST, port_lab)
            p0_ctrl = http_probe(config.CONTROL_CLIENT, config.HOST, port_lab)
            self.assertTrue(p0_lab["ok"], p0_lab)
            self.assertTrue(p0_ctrl["ok"], p0_ctrl)

            # 2. Real FP32 ONNX detector warms up and streams recorded Friday replay to Node B
            engine = ReplayEngine(self.sender, f"http://127.0.0.1:{port_b}", speed=20.0)
            try:
                engine.start()
                deadline = time.time() + 15.0
                pend = []
                while time.time() < deadline:
                    _, snap = _http_json(f"http://127.0.0.1:{port_b}/api/state")
                    pend = snap["node_b"]["pending_approvals"]
                    if pend:
                        break
                    time.sleep(0.2)
                engine.pause()
            finally:
                engine.stop()

            self.assertTrue(len(pend) >= 1, "Expected Node A FP32 ONNX replay to emit mapped alert for 172.16.0.1")
            alert_ev = pend[0]
            self.assertEqual(alert_ev["subject"], "172.16.0.1")
            self.assertEqual(alert_ev["target"], config.LAB_CLIENT)
            self.assertGreater(alert_ev["risk"], alert_ev["threshold_r_block"])

            # 5. Before approval, remote-only alert did NOT block lab client
            self.assertTrue(http_probe(config.LAB_CLIENT, config.HOST, port_lab)["ok"])

            # Operator header required on /api/approve
            code_no_hdr, _ = _http_json(
                f"http://127.0.0.1:{port_b}/api/approve", method="POST", body={"event_id": alert_ev["event_id"]}
            )
            self.assertEqual(code_no_hdr, 403)

            # 7. Approve block (use short 2s block via Enforcer directly after testing /api/approve, or approve then check)
            code_ok, app_resp = _http_json(
                f"http://127.0.0.1:{port_b}/api/approve",
                method="POST",
                body={"event_id": alert_ev["event_id"]},
                headers={config.OPERATOR_HEADER: "1"},
            )
            self.assertEqual(code_ok, 200)
            self.assertEqual(app_resp["approval_mode"], "human-approved")
            first_expires = app_resp["block"]["expires"]

            # Lab client 127.0.0.2 genuinely fails, control client 127.0.0.3 still succeeds!
            p_blk = http_probe(config.LAB_CLIENT, config.HOST, port_lab)
            p_ctrl = http_probe(config.CONTROL_CLIENT, config.HOST, port_lab)
            self.assertFalse(p_blk["ok"], "Expected 127.0.0.2 to fail during active block")
            self.assertTrue(p_ctrl["ok"], "Expected control client 127.0.0.3 to stay unblocked")

            # 9. Duplicate approval / duplicate alert does NOT extend the block
            code_dup, dup_resp = _http_json(
                f"http://127.0.0.1:{port_b}/api/approve",
                method="POST",
                body={"event_id": alert_ev["event_id"]},
                headers={config.OPERATOR_HEADER: "1"},
            )
            self.assertEqual(code_dup, 200)
            self.assertTrue(dup_resp["already"])
            self.assertEqual(state_b.enforcer.blocks[config.LAB_CLIENT]["expires"], first_expires)

            # 8a. Manual unblock restores access immediately
            code_unb, _ = _http_json(
                f"http://127.0.0.1:{port_b}/api/unblock",
                method="POST",
                body={"target": config.LAB_CLIENT},
                headers={config.OPERATOR_HEADER: "1"},
            )
            self.assertEqual(code_unb, 200)
            self.assertTrue(http_probe(config.LAB_CLIENT, config.HOST, port_lab)["ok"])

            # 4b. Adversarial HTTP checks against live /api/alerts endpoint
            bad_msg = self._build_msg(subject="172.16.0.1")
            bad_msg["detection"]["risk"] = 0.01  # tampered after signing
            c_tamp, r_tamp = _http_json(f"http://127.0.0.1:{port_b}/api/alerts", method="POST", body=bad_msg)
            self.assertEqual(c_tamp, 403)
            self.assertEqual(r_tamp["code"], "bad_signature")

            # 8b. Automatic expiry (2s block) restores access automatically
            res_ttl = state_b.enforcer.block(
                config.LAB_CLIENT, 2, event_id="b" * 32, approval_mode="human-approved", reason="expiry check"
            )
            self.assertTrue(res_ttl["ok"])
            self.assertFalse(http_probe(config.LAB_CLIENT, config.HOST, port_lab)["ok"])
            time.sleep(2.4)
            self.assertFalse(state_b.enforcer.is_blocked(config.LAB_CLIENT))
            self.assertTrue(http_probe(config.LAB_CLIENT, config.HOST, port_lab)["ok"])

        finally:
            srv_b.shutdown()
            cleanup_b()

        # 11. Model/checkpoint/windows hashes unchanged
        after_hashes = {
            "pt": sha256_file(config.CHECKPOINT),
            "onnx": sha256_file(config.CHECKPOINT.with_suffix(".onnx")),
            "windows": sha256_file(config.WINDOWS),
        }
        self.assertEqual(before_hashes, after_hashes)

    def test_refuses_missing_fp32_onnx_without_int8_fallback(self):
        fake_pt = self.rt / "fake.pt"
        fake_pt.write_bytes(b"not-used")
        (self.rt / "fake.int8.onnx").write_bytes(b"should-never-load")
        with self.assertRaises(FileNotFoundError):
            model_metadata(fake_pt, config.WINDOWS)


    def test_node_a_replay_controls_require_operator_header(self):
        """A cross-origin-style POST (no custom header) must not start, pause, reset or retune the replay."""
        import socket
        from node_a import NodeAServer, make_handler
        calls = []
        class FakeEngine:
            def start(self): calls.append("start")
            def pause(self): calls.append("pause")
            def reset(self, autostart=False): calls.append("reset")
            def set_speed(self, v): calls.append("speed")
            def snapshot(self): return {"status": "paused", "replay": {"speed": 1}}
        def free_port():
            with socket.socket() as s:
                s.bind(("127.0.0.1", 0)); return s.getsockname()[1]
        port_a, port_b, port_lab = free_port(), free_port(), free_port()
        srv_a = NodeAServer(("127.0.0.1", port_a), make_handler(FakeEngine()))
        threading.Thread(target=srv_a.serve_forever, daemon=True).start()
        srv_b, gate, state_b, cleanup_b = build_node_b(port=port_b, lab_port=port_lab,
            node_a_url=f"http://127.0.0.1:{port_a}", runtime_dir=self.rt, probe_period=0.0)
        threading.Thread(target=srv_b.serve_forever, daemon=True).start()
        try:
            for route in ("start", "pause", "reset", "speed"):
                code, _ = _http_json(f"http://127.0.0.1:{port_a}/replay/{route}", method="POST", body={})
                self.assertEqual(code, 403, route)
            self.assertEqual(calls, [], "unguarded POST reached the replay engine")
            code, _ = _http_json(f"http://127.0.0.1:{port_a}/replay/start", method="POST", body={},
                                 headers={config.OPERATOR_HEADER: "1"})
            self.assertEqual(code, 200)
            # Node B's operator proxy forwards the header, so the dashboard buttons still work.
            code, _ = _http_json(f"http://127.0.0.1:{port_b}/api/node-a/pause", method="POST", body={},
                                 headers={config.OPERATOR_HEADER: "1"})
            self.assertEqual(code, 200)
            self.assertEqual(calls, ["start", "pause"])
            code, _ = _http_json(f"http://127.0.0.1:{port_b}/api/node-a/reset", method="POST", body={})
            self.assertEqual(code, 403)  # Node B itself still refuses without the header
        finally:
            srv_a.shutdown(); srv_b.shutdown(); cleanup_b()

    def test_report_endpoint_is_read_only_and_rule_based(self):
        """GET /api/report and /api/report.md work without the operator header and take no input."""
        import socket
        def free_port():
            with socket.socket() as sk:
                sk.bind(("127.0.0.1", 0)); return sk.getsockname()[1]
        port_b, port_lab = free_port(), free_port()
        srv_b, gate, state_b, cleanup_b = build_node_b(port=port_b, lab_port=port_lab,
            node_a_url=f"http://127.0.0.1:{free_port()}", runtime_dir=self.rt, probe_period=0.0)
        threading.Thread(target=srv_b.serve_forever, daemon=True).start()
        try:
            code, rep = _http_json(f"http://127.0.0.1:{port_b}/api/report")
            self.assertEqual(code, 200)
            self.assertIn("No language model is used", rep["method"] + " ".join(sum((s["sentences"] for s in rep["sections"]), [])))
            req = urllib.request.Request(f"http://127.0.0.1:{port_b}/api/report.md")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                self.assertEqual(resp.status, 200)
                self.assertIn("text/markdown", resp.headers["Content-Type"])
                self.assertTrue(resp.read().decode().startswith("# Demo report"))
            # a POST to the report path is not a route (nothing can be injected through it)
            code, _ = _http_json(f"http://127.0.0.1:{port_b}/api/report", method="POST", body={"x": 1},
                                 headers={config.OPERATOR_HEADER: "1"})
            self.assertEqual(code, 404)
        finally:
            srv_b.shutdown(); cleanup_b()

if __name__ == "__main__":
    unittest.main()
