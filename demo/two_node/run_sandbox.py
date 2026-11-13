"""Run the REAL two-node demo on synthetic data. No dataset, checkpoint or trained model is needed.

    python run_sandbox.py --reset-state --autostart                  # human approval (default)
    python run_sandbox.py --reset-state --autostart --autonomous-lab # explicit bounded lab mode

On first run it builds a synthetic dataset and a toy model (about 2 minutes, CPU only), then starts the
unchanged Node A, Node B, policy gate and enforcer on 127.0.0.1. Everything the dashboard shows is
labelled SANDBOX. The synthetic results say nothing about detection quality. See sandbox/README.md.
"""
import os
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "sandbox"))
import make_sandbox  # noqa: E402

build = Path(os.environ.get("CYBERNCM_SANDBOX_DIR", HERE / "sandbox" / "build"))
checkpoint, _onnx, windows = make_sandbox.build(build)
os.environ.update({
    "CYBERNCM_SANDBOX": "1",
    "CYBERNCM_CHECKPOINT": str(checkpoint),
    "CYBERNCM_WINDOWS": str(windows),
    "CYBERNCM_SUBJECT": make_sandbox.SUBJECT,
    "CYBERNCM_PROTECTED_RECORDED": make_sandbox.PROTECTED,
    # keys and state of the sandbox are kept apart from any real-data run
    "CYBERNCM_DEMO_RUNTIME": os.environ.get("CYBERNCM_DEMO_RUNTIME", str(HERE / "runtime-sandbox")),
})
sys.path.insert(0, str(HERE))
runpy.run_path(str(HERE / "run_demo.py"), run_name="__main__")
