"""Independent CLI probe for the isolated lab HTTP service on 127.0.0.1:18080."""
import argparse
import json
import config
from node_b import http_probe

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Send one real HTTP GET each from the lab client (127.0.0.2) and control client (127.0.0.3).")
    ap.add_argument("--port", type=int, default=config.LAB_PORT)
    args = ap.parse_args()
    out = {
        "lab_client_127_0_0_2": http_probe(config.LAB_CLIENT, config.HOST, args.port),
        "control_client_127_0_0_3": http_probe(config.CONTROL_CLIENT, config.HOST, args.port),
    }
    print(json.dumps(out, indent=2))
