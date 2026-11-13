"""Key generation, explicit trust configuration, and runtime cleanup for the two-node demo.

Read-only artifacts (checkpoint, FP32 ONNX export, windows.npz) are hashed, never modified.
"""
import argparse
import json
import shutil
from pathlib import Path

import config
from protocol import load_or_create_key, node_id_for, pub_raw, sha256_file


def model_metadata(checkpoint_path: Path = config.CHECKPOINT, windows_path: Path = config.WINDOWS) -> dict:
    onnx_path = checkpoint_path.with_suffix(".onnx")
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
    if not onnx_path.is_file():
        raise FileNotFoundError(
            f"FP32 ONNX export required: {onnx_path}. INT8 is experimental and is never used as a fallback."
        )
    if not windows_path.is_file():
        raise FileNotFoundError(f"Canonical windows file not found: {windows_path}")
    return {
        "format": "onnx-fp32",
        "checkpoint_path": str(checkpoint_path),
        "onnx_path": str(onnx_path),
        "windows_path": str(windows_path),
        "checkpoint_sha256": sha256_file(checkpoint_path),
        "onnx_sha256": sha256_file(onnx_path),
        "windows_sha256": sha256_file(windows_path),
    }


def ensure_setup(runtime_dir: Path = config.RUNTIME, checkpoint_path: Path = config.CHECKPOINT,
                 windows_path: Path = config.WINDOWS, reset_keys: bool = False) -> dict:
    keys_dir = runtime_dir / "keys"
    state_dir = runtime_dir / "state"
    trust_file = runtime_dir / "trusted_senders.json"
    if reset_keys and keys_dir.exists():
        shutil.rmtree(keys_dir)
    keys_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)

    key_a = load_or_create_key(keys_dir / "node_a.key")
    key_b = load_or_create_key(keys_dir / "node_b.key")
    pub_a = pub_raw(key_a)
    pub_b = pub_raw(key_b)
    id_a = node_id_for(pub_a)
    id_b = node_id_for(pub_b)

    meta = model_metadata(checkpoint_path, windows_path)
    trust = {
        id_a: {
            "name": "site-a-sim",
            "public_key_hex": pub_a.hex(),
            "allowed": ["alert"],
            "expected_model_onnx_sha256": meta["onnx_sha256"],
        }
    }
    tmp = trust_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(trust, indent=2))
    tmp.replace(trust_file)

    return {
        "node_a_id": id_a,
        "node_b_id": id_b,
        "trust_file": str(trust_file),
        "state_dir": str(state_dir),
        "model": meta,
    }


def reset_state(runtime_dir: Path = config.RUNTIME):
    state_dir = runtime_dir / "state"
    if state_dir.exists():
        shutil.rmtree(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Initialize keys and trust config for the two-node demo.")
    ap.add_argument("--reset-state", action="store_true", help="Clear sequence numbers, replay cache, and block journal.")
    ap.add_argument("--reset-keys", action="store_true", help="Regenerate Ed25519 keys and trusted_senders.json.")
    args = ap.parse_args()
    if args.reset_state:
        reset_state()
    info = ensure_setup(reset_keys=args.reset_keys)
    print(json.dumps(info, indent=2))
