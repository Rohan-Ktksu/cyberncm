# Five-Minute Presentation Walkthrough (14 November 2026)

Target runtime: **5 minutes**.
Before going on stage, run:
```powershell
cd demo/two_node
python run_demo.py --reset-state
```
Open `http://127.0.0.1:18100/` in the browser.

---

## Minute 0:00 – 0:45 — Setup & Honest Framing
- **Show:** Top banner, topology (`Node A` and `Node B` on `127.0.0.1`), and the **Independent HTTP Probes** panel.
- **Point out:**
  - Both `127.0.0.2` (lab client) and `127.0.0.3` (control client) are getting `HTTP 200` from `http://127.0.0.1:18080/`.
  - `Node A` uses the frozen FP32 ONNX model (`onnx-fp32`, SHA-256 shown); zero online learning.
  - **Say clearly:** *"This is a two-node cooperative prototype on localhost. Node A is replaying recorded CIC-IDS2017 Friday 5-second flow windows, and Node B gates a mapped lab client `127.0.0.2`. We are not claiming the detector inspected `127.0.0.2`'s live traffic, and this is not consensus or federated learning."*

## Minute 0:45 – 1:45 — Real Detection & Signed Alert Exchange
- **Action:** Click **Start replay** on Node A (speed `10×`).
- **Show (within ~5 seconds):**
  - `Node A` scores real recorded windows starting at offset `25000 s` and hits `172.16.0.1` (`risk ~0.999 > r_block 0.5974`, dataset ground-truth label `DDoS`).
  - `Node A` signs `NCMThreatDirective` v1.2.0 (`Ed25519` + `event_id` + `monotonic_seq` + model SHA-256) and sends it to `Node B`.
  - **Point out in Node B's table:** Other hosts (e.g., `192.168.10.8`) also trigger alerts and pass signature verification—and Node B's policy **rejects** them because they are not mapped to the lab-client allowlist. That illustrates why false alarms (6.33% of benign windows on Friday) require strict target scoping.

## Minute 1:45 – 2:30 — Remote Alert Alone Never Auto-Blocks
- **Show:** `Policy Gate (Node B)` shows `PENDING_APPROVAL` for `172.16.0.1 -> 127.0.0.2`.
- **Show:** `Real Enforcement State` still says **`Allowing traffic`**, and the live probe for `127.0.0.2` still returns **`HTTP 200`**.
- **Say:** *"Because Node B has no independent local sensor for the recorded subject, a remote alert alone never triggers a block. It waits for explicit operator approval (`human-approved`), bounded to `127.0.0.2` on port `18080` for at most 30 seconds."*

## Minute 2:30 – 3:45 — Human-Approved Block & Real Connection Failure
- **Action:** Click **Approve 30s block (human-approved)**.
- **Show immediately:**
  - `Real Enforcement State` flips to **`Blocked`** with a live 30 s countdown.
  - **Independent HTTP Probes:**
    - `127.0.0.2` (lab client) **fails** (`RemoteDisconnected: Remote end closed connection without response`), and `TCP Resets` increments.
    - `127.0.0.3` (control client) **continues getting `HTTP 200`** — proving the block is tightly scoped to the approved lab client and does not touch host/public networking.
  - **Before / During** probe cards show the transition side by side.
- *(Optional second terminal)* Run `python probe_client.py` to show raw JSON probe results outside the browser.

## Minute 3:45 – 4:30 — Expiry / Manual Unblock & Recovery
- **Action:** Either click **Manual unblock now** OR let the 30 s TTL expire automatically (if time permits; clicking **Manual unblock now** is immediate for live pacing, and the automated test verifies 2 s TTL expiry).
- **Show:**
  - `Real Enforcement State` returns to **`Allowing traffic`**.
  - **3. After expiry / unblock** probe card returns to **`HTTP 200`**.

## Minute 4:30 – 5:00 — Verification Guarantees & Limits
- **Summarize honestly:**
  - Tampered, expired, replayed (`event_id` and `monotonic_seq`), and unknown-sender alerts are rejected by `Verifier` (tested in `test_two_node.py`).
  - Duplicate approvals do not extend an active block.
  - Restart/crash cleanup clears leftover journal entries on startup.
  - **What is NOT claimed:** production readiness, automatic blocking safety, consensus, or federated learning.
