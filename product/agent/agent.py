"""cyberncm agent (single site, shadow mode only: it never blocks anything).
  python agent.py enrol --server URL --token TOKEN [--config agent.json]
  python agent.py run --flows flows.csv [--config agent.json] [--learn-minutes 1440] [--base-model PATH]
`run` replays a flow file (CSV, columns in flows.py) in time order: the first --learn-minutes of traffic are the learning period (the site's normal),
then every window is scored. A live follow mode (reading flows as they arrive) is not built yet."""
import argparse, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from client import Client, VERSION
from detector import Detector
from flows import ip_str, read_flows, windows

HERE = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.join(HERE, "model", "base_gru64.pt")


def run(client: Client, flows_path: str, learn_minutes: float, base_model: str = BASE, batch_seconds: float = 300.0, log=print):
    det = Detector(base_model, learn_seconds=learn_minutes * 60); X, src, t = windows(read_flows(flows_path)); log(f"{len(X)} windows from {flows_path}")
    t0, sent = float(t.min()), 0
    for lo in np.arange(t0, float(t.max()) + batch_seconds, batch_seconds):
        sel = (t >= lo) & (t < lo + batch_seconds)
        if not sel.any(): continue
        events = det.process(X[sel], src[sel], t[sel])
        for e in events:
            e["detail"]["src_ip"] = ip_str(e["src"]); e["src"] = ip_str(e["src"])
            if e["kind"] == "shadow_block": e["signature"] = client.directive_signature(e)
        code, _ = client.signed_post("/api/agent/heartbeat", {"state": det.state, "windows_seen": det.seen, "learn_progress": det.learn_progress, "info": {"version": VERSION, "threshold": det.threshold, "mode": "shadow"}})
        if code != 200: raise RuntimeError(f"heartbeat refused ({code})")
        if events:
            code, out = client.signed_post("/api/agent/events", {"events": events}); sent += out.get("stored", 0) if code == 200 else 0
        log(f"t={lo - t0:7.0f}s state={det.state:8s} windows={det.seen:6d} events_sent={sent}")
    return det


def main(argv=None):
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("enrol"); e.add_argument("--server", required=True); e.add_argument("--token", required=True); e.add_argument("--config", default="agent.json")
    r = sub.add_parser("run"); r.add_argument("--flows", required=True); r.add_argument("--config", default="agent.json"); r.add_argument("--learn-minutes", type=float, default=1440.0); r.add_argument("--base-model", default=BASE)
    a = ap.parse_args(argv)
    if a.cmd == "enrol":
        out = Client(a.config).enrol(a.server, a.token); print(f"enrolled as {out['agent_id']} for site '{out['site_name']}'; config saved to {a.config}")
    else:
        run(Client(a.config), a.flows, a.learn_minutes, a.base_model)


if __name__ == "__main__":
    main()
