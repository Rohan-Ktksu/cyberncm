"""Node B's policy: may a verified remote alert lead to a block, and on whom?

The target always comes from Node B's own configuration (SUBJECT_MAP and the lab allowlist), never from the
message. A remote alert alone never blocks: Node B has no independent sensor for the recorded subject, so
an operator must approve, and the block is labelled human-approved.
"""
import ipaddress
from dataclasses import dataclass, field

import config


@dataclass
class Decision:
    action: str                 # REJECT | PENDING_APPROVAL | BLOCK | ALREADY_BLOCKED
    reason: str
    target: str | None = None
    ttl_seconds: int = 0
    approval_mode: str = "none"  # none | human-approved
    scope: dict = field(default_factory=dict)


def target_allowed(ip: str, allowlist=config.LAB_CLIENT_ALLOWLIST, protected=config.PROTECTED_ADDRESSES) -> tuple[bool, str]:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False, "not an IP address"
    if addr.version != 4 or not addr.is_loopback:
        return False, "only loopback lab addresses can be targeted"
    if str(addr) in protected:
        return False, "protected address (management, control client or host)"
    if str(addr) not in allowlist:
        return False, "not on the lab-client allowlist"
    return True, "allowlisted lab client"


def decide(msg: dict, verified: dict, *, operator_approved: bool, local_evidence=None, is_blocked=lambda ip: False,
           subject_map=config.SUBJECT_MAP, allowlist=config.LAB_CLIENT_ALLOWLIST) -> Decision:
    ea = msg["enforcement_action"]
    scope = {"service": "lab-http", "dst": f"{config.HOST}:{config.LAB_PORT}", "proto": "tcp"}
    if ea["directive_type"] != "OPTIMISTIC_QUARANTINE_DROP":
        return Decision("REJECT", f"{ea['directive_type']} is not acted on in this demo")
    subject = ea["src_cidr"].split("/")[0]
    target = subject_map.get(subject)
    if target is None:
        return Decision("REJECT", f"subject {subject} is not mapped to an allowlisted lab client")
    ok, why = target_allowed(target, allowlist)
    if not ok:
        return Decision("REJECT", f"mapped target {target}: {why}")
    expected = verified.get("expected_model_onnx_sha256")
    if expected and msg["model"]["onnx_sha256"] != expected:
        return Decision("REJECT", "model hash differs from the model registered for this sender")
    det = msg["detection"]
    if det["input_mode"] not in config.ALLOWED_INPUT_MODES_FOR_ACTION:
        return Decision("REJECT", f"input mode {det['input_mode']} is never acted on")
    if not det["risk"] > det["threshold_r_block"]:
        return Decision("REJECT", "reported risk is not above the reported quarantine threshold")
    ttl = min(int(ea["ttl_seconds"]), config.MAX_BLOCK_SECONDS)
    if is_blocked(target):
        return Decision("ALREADY_BLOCKED", "target already blocked; block is not extended", target, 0, "none", scope)
    if local_evidence is None and not operator_approved:
        return Decision("PENDING_APPROVAL", "remote alert only: no independent local evidence at Node B; "
                        "operator approval required", target, ttl, "none", scope)
    if operator_approved:
        return Decision("BLOCK", "operator approved a verified remote alert", target, ttl, "human-approved", scope)
    return Decision("PENDING_APPROVAL", "local evidence path is not implemented in this demo", target, ttl, "none", scope)
