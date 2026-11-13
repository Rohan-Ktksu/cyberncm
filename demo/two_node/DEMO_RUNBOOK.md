# Two-Node Cooperative Demo — Runbook (14 November 2026)

> **Honest scope:** This is a two-node cooperative prototype running as two local Python processes on `127.0.0.1`. It demonstrates signed alert exchange, independent verification, human-approved bounded policy, and real userspace TCP gating of an isolated lab client. It is **not** decentralized consensus, federated learning, live packet capture, or a proven production firewall (see `research/G1.md`).

## 1. Architecture & Safety Boundaries

| Component | Process / Port | Role |
|---|---|---|
| **Node A (`node_a.py`)** | `127.0.0.1:18200` | Runs frozen FP32 ONNX model (`ncm_gru64_s0.onnx`) on recorded CIC-IDS2017 Friday windows (`windows.npz`), signs `NCMThreatDirective` v1.2.0 messages with Ed25519, and POSTs them to Node B. |
| **Node B (`node_b.py`)** | `127.0.0.1:18100` | Verifies Ed25519 signature, schema, trusted sender, freshness, expiry, scope, and monotonic replay state; evaluates local policy; requires operator approval; serves the dashboard at `/`. |
| **Lab HTTP Gate (`LabGate`)** | `127.0.0.1:18080` | Isolated HTTP service. `Enforcer` drops connections (`SO_LINGER` TCP reset) only for `LAB_CLIENT` (`127.0.0.2`) when an approved block is active (max 30 s). |
| **Control Client** | `127.0.0.3` (source IP) | Never blockable (`PROTECTED_ADDRESSES`). Proves the block is narrow and `127.0.0.1:18080` remains healthy for other clients. |

**Host network protection:** Windows Firewall, campus/public interfaces, and routing tables are never modified. All sockets bind to `127.0.0.1`.

## 2. Prerequisites & Read-Only Artifacts

Run with the Python 3.12 environment containing `numpy`, `onnxruntime`, `torch`, `jsonschema`, and `cryptography`.

Read-only artifacts (hashed at startup, never modified):
- `artifacts/ncm_gru64_s0.pt` (`SHA-256: 6fbe44e4f23c77f49fa6d3b3fc193d69c04cb5338b3cecb833518f1d748aecff`)
- `artifacts/ncm_gru64_s0.onnx` (`SHA-256: 228f207cf44871a845867c3153aa2b61851362df4b7199d84bbe735582e2b945`)
- `data/windows.npz` (`SHA-256: 0f8a383e5b19c05123d23f89f7dbc526a00f15e54afbe9bc5292685f8bc2bea5` — verified via `bootstrap.py`)

Override paths via environment variables if running from another directory:
- `CYBERNCM_CHECKPOINT`, `CYBERNCM_WINDOWS`, `CYBERNCM_DEMO_RUNTIME`.

## 3. Setup, Start, Reset, Probe & Cleanup Commands

All commands below assume working directory `demo/two_node`.

### Initial setup (generates Ed25519 keys & `trusted_senders.json` in git-ignored `runtime/`)
```powershell
cd demo/two_node
python bootstrap.py
```

### Start the live demo (single command launching Node B + Node A as separate processes)
```powershell
python run_demo.py --reset-state --autostart
```
Then open the dashboard in a browser:
`http://127.0.0.1:18100/`

To start paused (so you click **Start replay** live on stage):
```powershell
python run_demo.py --reset-state
```

### Start Node B and Node A in two separate terminals (optional)
Terminal 1 (Node B + Lab Gate + Dashboard):
```powershell
cd demo/two_node
python node_b.py
```
Terminal 2 (Node A):
```powershell
cd demo/two_node
python node_a.py --autostart
```

### Independent CLI probe (optional second-terminal proof)
Sends one real HTTP GET from `127.0.0.2` (lab client) and one from `127.0.0.3` (control client) to `http://127.0.0.1:18080/`:
```powershell
cd demo/two_node
python probe_client.py
```

### Reset state between rehearsals
```powershell
cd demo/two_node
python bootstrap.py --reset-state
```
(Or click **Reset** in the dashboard to rewind Node A's replay to Friday offset `25000.0 s`.)

### Cleanup & Crash Recovery
- **Normal stop:** Press `Ctrl+C` in the launcher or node terminal. `atexit` and `SIGINT`/`SIGTERM` handlers call `enforcer.unblock(None, why="shutdown")`, stop the reaper thread, and close `LabGate`.
- **Crash recovery:** `Enforcer` persists active rules to `runtime/state/enforcer_journal.json`. On the next start, `Enforcer._clear_previous_run()` clears any leftover rules from a prior crashed run instead of restoring them, and logs `startup_cleanup` in the dashboard.
- **Full state wipe:** `python bootstrap.py --reset-state --reset-keys` removes `runtime/state/` and regenerates keys/trust.

## 4. Recorded Fallback Mode

If live processes cannot run during presentation, serve the static directory and open the dashboard with `?fallback=1`:
```powershell
python -m http.server 18100 --bind 127.0.0.1 --directory <local path>
```
Open: `http://127.0.0.1:18100/dashboard.html?fallback=1`

This displays a red **`RECORDED FALLBACK TRACE`** banner and cycles through 4 saved snapshots (`recorded_fallback.json`) captured from an actual live two-process run.

## 5. Verification Tests & Observed Results

Run the automated test suite and live two-process verification:
```powershell
cd demo/two_node
python -m unittest test_two_node.py -v
python verify_live_two_process.py
```

Observed results on this machine (2026-11-13):
- `ncm/test_ncm.py`: `all checks passed`.
- `demo/two_node/test_two_node.py`: **5 tests ran in 8.101s, OK**:
  - `test_valid_and_rejected_messages`: verifies valid Ed25519/v1.2.0 message, rejects tampered payload (`bad_signature`), duplicate `event_id` (`replay`), reused `monotonic_seq` (`replay`), expired `expires_ns` (`expired`), and unregistered key (`unknown_sender`).
  - `test_policy_safeguards`: verifies remote-only returns `PENDING_APPROVAL`, approved mapped subject targets `127.0.0.2` (`human-approved`, `<= 30 s`), unmapped/protected targets (`192.168.10.8`, `127.0.0.1`, `127.0.0.3`, `8.8.8.8`, `0.0.0.0`) are rejected by policy and `Enforcer`, and `test-injection` input mode is rejected by policy.
  - `test_startup_cleanup_clears_stale_blocks`: verifies leftover `enforcer_journal.json` entries are cleared on startup.
  - `test_refuses_missing_fp32_onnx_without_int8_fallback`: verifies missing `.onnx` raises `FileNotFoundError` and never falls back to `.int8.onnx`.
  - `test_end_to_end_real_detector_and_enforcement`: runs real FP32 ONNX replay against `LabGate`, confirms initial HTTP 200 for `127.0.0.2` and `127.0.0.3`, confirms remote-only does not block, verifies `403` without `X-CyberNCM-Operator`, verifies tampered `/api/alerts` returns `403 bad_signature`, approves block, confirms `127.0.0.2` genuinely fails while `127.0.0.3` stays `200`, confirms duplicate approval does not extend expiry, verifies recovery after manual unblock AND after 2s automatic expiry, and confirms SHA-256 hashes of `.pt`, `.onnx`, and `windows.npz` remain identical.
- `demo/two_node/verify_live_two_process.py`: exercised separate `node_b.py` and `node_a.py` OS processes; verified `127.0.0.2` HTTP 200 before (`2.6 ms`) -> `RemoteDisconnected` during block (`0.87 ms`, while `127.0.0.3` got HTTP 200 in `4.64 ms`) -> HTTP 200 after unblock (`1.54 ms`); captured 4 snapshots into `recorded_fallback.json`.

## 6. Known Limitations

1. **Simulated single-host topology:** Both nodes and both test clients run on `127.0.0.1`.
2. **Recorded replay, not live packet capture:** Node A scores recorded CIC-IDS2017 Friday 5-second windows (`25000–26260 s`) and maps `172.16.0.1` to lab client `127.0.0.2`. The model does not inspect `127.0.0.2`'s live HTTP requests.
3. **Human-approved policy only:** Node B has no independent local flow sensor for `172.16.0.1`, so remote alerts always require explicit operator approval (`human-approved`).
4. **Userspace connection gate:** Enforcement gates `LabGate` (`127.0.0.1:18080`), not the Windows host firewall or kernel XDP.
5. **Underlying model false alarms:** In the full Friday FP32 replay, simulated quarantine covered 6.33% of benign windows (and 43.5% of attack windows). Unmapped subjects in the replay (`192.168.10.8`, `192.168.10.14`, `192.168.10.15`) still trigger Node A alerts during the segment and are visibly rejected by Node B's allowlist policy.


## Independent review fixes — 13 November 2026

 approval-lifecycle review found that already-received alerts could be approved after expiry or reused after unblock. Approval now rechecks freshness and pending state; consumed, superseded, and cleared alerts cannot create a new block. Repeated approval while the original block is active is an idempotent no-op. Approval, supersession, and manual-unblock state changes are serialized; reentrant locking allows the existing enforcer event callbacks.

Verification: nine tests pass, including expired pending alerts, reuse after manual unblock/TTL expiry, superseded alerts, and eight simultaneous duplicate approvals producing exactly one block. The live two-process verification passes with the lab client failing only during the approved block, the control client reachable, and recovery after unblock. Model/data hashes remain unchanged. This does not add live packet sensing, kernel firewall enforcement, or production readiness. Browser rendering was not independently rechecked in this review.


## Optional autonomous lab mode (separate feature, not G1 approval)

The default launcher remains human-approved even if an old environment variable is set. Explicit opt-in:

```powershell
cd demo/two_node
python run_demo.py --reset-state --autostart --autonomous-lab
```

Open http://127.0.0.1:18100/. The red AUTONOMOUS LAB MODE banner explains the scope and exposes **Disable automation and unblock**. A real FP32 alert from the recorded dataset can automatically close the mapped lab client's connections. The model has not detected that client's live HTTP traffic, and Node B has no independent local flow sensor.

Limits: only the configured 127.0.0.2 client on the lab HTTP listener; only trusted, signed, fresh recorded-replay alerts matching the enrolled model hash; at most 10 seconds; one automatic block per target per Node B process. Further alerts cannot prolong or recreate automatic blocks after expiry/unblock. A fresh explicit process startup grants a new one-shot allowance. This budget is per process, not durable across opt-in restarts. No model training, Windows firewall changes, campus/public networking, consensus, or G1 claim.

The disable button immediately disarms automation and clears active lab blocks. There is no remote API to rearm it. Subsequent valid alerts require human approval. The standard Unblock button clears the current block but does not rearm the spent automatic allowance. Ctrl+C stops both nodes and removes the userspace gate.

Verification:
```powershell
python test_two_node.py
python verify_autonomous_lab.py
```
Twelve tests passed, including one-shot budget, expiry, replay rejection, protected client, test-injection rejection and kill switch. The new two-process verifier runs the real FP32 detector twice: automatic expiry and emergency disable. Both produced a real lab-client failure, kept the control client reachable, restored access, and did not automatically reblock. It also verifies that the model/checkpoint/dataset hashes do not change. Small captured results: verification/autonomous_lab.json. Browser rendering has not been independently rehearsed; the endpoint itself was exercised over HTTP.

Browser rehearsal found and fixed automatic-mode and configured-port labels. Enforcement now shows a confirmed block only after a fresh failed lab probe and successful control probe. Block durations use a monotonic clock; a backward wall-clock correction cannot prolong them. Twelve tests and both real-process autonomous scenarios pass. The corrected presentation and a self-contained recorded backup are in <local path> This does not establish G1 safety.
