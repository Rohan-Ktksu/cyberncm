# cyberncm single-site product (plan step 41, first slice)

Built after gate G1 (`research/G1.md`), which recommends a single-site detector in alert and shadow mode and not the mesh. **Shadow mode is the only mode: nothing here blocks anything, and nothing here shares data between sites.** Plan steps 42 and 43 (two agents exchanging directives, gossip, consensus, federated learning) are **not built**, because R12 found that sharing does not pay with the current alert rule.

## What it does

1. **Sign up and add a site** in the console (`product/console/index.html`, served at `/`). Adding a site gives a one-time **enrolment token** (valid 24 hours) and an install command.
2. **Run the agent** (`product/agent/agent.py`) where the site's flow records are. `enrol` generates an Ed25519 key pair on the machine and registers its public key; `run` reads a flow file, **learns the site's normal traffic** for a configurable period, then scores every window and sends signed heartbeats and events.
3. **See it connect:** the site page shows the agent's state (waiting, connected and learning, connected in shadow mode, offline), windows seen, learning progress, recent alerts and the **would-block list** (each entry signed by the agent, with an expiry), always under the banner "nothing is blocked on your network".

## Run it

```
pip install -r requirements.txt -r product/requirements.txt
CYBERNCM_DB=console.db uvicorn product.server.app:create_app --factory --port 8000      # console at http://127.0.0.1:8000
python product/agent/agent.py enrol --server http://127.0.0.1:8000 --token <token from the console>
python product/agent/agent.py run --flows product/sample/flows_sample.csv.gz --learn-minutes 20
python -m pytest product/tests -q
```

The agent input is a CSV of flow records with the columns listed in `product/agent/flows.py` (IPv4 addresses as integers, start time in seconds, durations in microseconds; the 32 features are built by `ncm/prep.py`, the same code as the research). `product/sample/flows_sample.csv.gz` is a 70-minute slice of CIC-IDS2017 (Tuesday, 73,013 flows, with an FTP brute-force attack that starts 28 minutes in; the file has a ground-truth `family` column that the agent ignores).

## What the tests show

`product/tests/test_product.py` (6 tests): password hashing, sign-up, login lockout after 5 failures, sites private to their owner, enrolment token single use and expiry, signed-request replay and tampering refused, and the **end-to-end path**: sign up, add a site, enrol an agent, run the agent on the sample, check the site is in shadow mode with alerts. On the sample, with a 20-minute learning period, the would-block list contains **172.16.0.1** (the attacker) **and 192.168.10.8** (a benign host): the detector's false alerts (research/R4) show here as well. This is a demonstration on one lab slice, not a measurement.

## Security notes

- Passwords: scrypt with a random salt; sessions: random tokens stored only as SHA-256, `HttpOnly`, `SameSite=Strict` (and `Secure` when the public URL is https), 7 days.
- Agents: every request is signed (Ed25519 over agent id, timestamp, a strictly increasing sequence number and the body hash); timestamps more than 5 minutes off and replayed or out-of-order sequence numbers are refused. The enrolment token is stored hashed, works once and expires in 24 hours. The private key stays in the agent's config file (mode 600).
- Isolation: a site is visible only to the account that created it (other accounts get 404).
- The console renders server data with `textContent` only, no `innerHTML`.

## Limits, stated plainly

- **Learning period:** the agent's default is 24 hours of traffic, but R11 did not establish how long a real site needs (10 minutes was the lab minimum); the sample run uses 20 minutes for demonstration only. **Do not describe any duration as validated.**
- **Replay only:** `run` reads a file in time order; a live "follow" mode and a flow exporter are not built. Flow records must already contain the CICFlowMeter-style fields (packet length statistics, TCP flag counts, initial window).
- **History is truncated to 32 windows per source** in the agent (the research code uses the whole day), and the agent uses PyTorch (not the INT8 ONNX step of R9).
- **Poisoning (R7c):** if attack traffic is in the learning period, that attack can go undetected; the learning period must be a period the owner has confirmed clean. The agent does not check this.
- **No enforcement and no mesh:** the would-block list is informational. The alert rule blocks far too many benign hosts to be used for blocking (R4, R7d).
- **Console and API are a first slice:** no email verification, no password reset, no rate limit beyond the login lockout (kept in memory, lost on restart), one agent per site, SQLite, single process. Not hardened for the open internet.
- **Browser check (author, 2026-11-12, Playwright with Chromium):** sign-up, adding a site, the one-time install command, an agent enrolling (a stand-in agent using the real signing client, with made-up events, since the agent's model needs PyTorch), the page updating by itself from "Waiting" to "Connected, learning" to "Connected, shadow mode" with its would-block list, and a 360 px layout without sideways page scroll all worked. Not checked: other browsers, a screen reader, full keyboard-only use (controls are native buttons, links and inputs with visible focus), the dark theme, and any real flow data through the browser.
