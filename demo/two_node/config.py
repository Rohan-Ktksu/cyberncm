"""Fixed configuration for the two-node demo. Nothing here is taken from message content.

Every address is on the loopback interface of one laptop. The two "sites" are simulated: two processes.
"""
import ipaddress
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
RUNTIME = Path(os.environ.get("CYBERNCM_DEMO_RUNTIME", HERE / "runtime"))   # keys and state, git-ignored
KEYS = RUNTIME / "keys"
STATE = RUNTIME / "state"
TRUST_FILE = RUNTIME / "trusted_senders.json"
SCHEMA_FILE = HERE / "schema" / "ncm-threat-directive-1.2.0.json"

# Frozen detector artifacts (read only). Override with environment variables if they live elsewhere.
CHECKPOINT = Path(os.environ.get("CYBERNCM_CHECKPOINT", str(REPO / "artifacts" / "ncm_gru64_s0.pt")))
WINDOWS = Path(os.environ.get("CYBERNCM_WINDOWS", str(REPO / "data" / "windows.npz")))

# Ports (all bound to 127.0.0.1 only)
HOST = "127.0.0.1"
NODE_A_PORT = int(os.environ.get("CYBERNCM_NODE_A_PORT", 18200))   # Node A status
NODE_B_PORT = int(os.environ.get("CYBERNCM_NODE_B_PORT", 18100))   # Node B: alert inbox, dashboard, operator API
LAB_PORT = int(os.environ.get("CYBERNCM_LAB_PORT", 18080))         # isolated lab HTTP service behind Node B's gate

# Lab clients: distinct loopback source addresses on the same machine.
LAB_CLIENT = "127.0.0.2"     # the only address enforcement may target
CONTROL_CLIENT = "127.0.0.3"  # never targeted; shows the block is narrow
LAB_CLIENT_ALLOWLIST = frozenset({LAB_CLIENT})

# Never blockable, even if someone edits the allowlist: management/dashboard address and anything off-loopback.
PROTECTED_ADDRESSES = frozenset({"127.0.0.1", CONTROL_CLIENT, "0.0.0.0"})

# Demo mapping: a recorded-dataset subject -> a lab client. The detector never saw the lab client's traffic.
# Sandbox mode (synthetic traffic and a toy model, no real data): see sandbox/README.md
SANDBOX = os.environ.get("CYBERNCM_SANDBOX", "0") == "1"
SUBJECT_MAP = {os.environ.get("CYBERNCM_SUBJECT", "172.16.0.1"): LAB_CLIENT}

MAX_BLOCK_SECONDS = 30          # hard cap on any block
MAX_ALERT_LIFETIME_S = 120      # expires_ns - timestamp_ns may not exceed this
CLOCK_SKEW_S = 30               # accepted future/past skew on timestamp_ns
ALLOWED_INPUT_MODES_FOR_ACTION = frozenset({"recorded-replay", "live"})  # "test-injection" is verified but never acted on

# Replay segment (CIC-IDS2017 Friday, offsets in seconds from the first window of the day)
REPLAY_DAY = 4
REPLAY_START = 25000
REPLAY_DURATION = 1260
REPLAY_SPEED = 10.0             # 5 s recorded window every 0.5 s of wall time
PROTECTED_RECORDED = [ipaddress.ip_network(os.environ.get("CYBERNCM_PROTECTED_RECORDED", "192.168.10.3/32"))]  # same protected prefix as ncm/stream.py

OPERATOR_HEADER = "X-CyberNCM-Operator"   # required on operator POSTs (forces a CORS preflight a page cannot pass)

# Explicit lab-only opt-in. The launcher clears inherited values unless its flag is passed.
AUTONOMOUS_LAB = os.environ.get("CYBERNCM_AUTONOMOUS_LAB", "0") == "1"
AUTONOMOUS_BLOCK_SECONDS = 10
