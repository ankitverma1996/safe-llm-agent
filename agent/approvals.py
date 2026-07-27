"""
Approval request persistence.

Every mutation/money-tier action is written to disk the moment it's
*proposed*, before it executes -- not after. This is what makes the
system safe across restarts: if the process crashes or restarts while
an approval is pending, it reloads the pending request from disk and
re-announces it, rather than either silently losing it or (worse)
silently re-executing it as if it had already been approved.
"""

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Dict, Optional

APPROVALS_FILE = os.environ.get("APPROVALS_FILE", "approvals_state.json")


@dataclass
class ApprovalRequest:
    id: str
    tool_name: str
    args: dict
    tier: str
    status: str  # "pending" | "approved" | "rejected" | "executed"
    created_at: float
    code: str  # the code the human must type back to approve


def _load_all() -> Dict[str, dict]:
    if not os.path.exists(APPROVALS_FILE):
        return {}
    with open(APPROVALS_FILE, "r") as f:
        return json.load(f)


def _save_all(data: Dict[str, dict]) -> None:
    with open(APPROVALS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def create_approval(tool_name: str, args: dict, tier: str) -> ApprovalRequest:
    req = ApprovalRequest(
        id=str(uuid.uuid4())[:8],
        tool_name=tool_name,
        args=args,
        tier=tier,
        status="pending",
        created_at=time.time(),
        code=str(uuid.uuid4())[:6].upper(),
    )
    data = _load_all()
    data[req.id] = asdict(req)
    _save_all(data)  # persisted before anything executes
    return req


def get_pending() -> Dict[str, ApprovalRequest]:
    data = _load_all()
    return {
        rid: ApprovalRequest(**r) for rid, r in data.items() if r["status"] == "pending"
    }


def resolve(approval_id: str, submitted_code: str) -> Optional[ApprovalRequest]:
    """
    Approve a pending request if the submitted code matches. Returns
    the updated request, or None if not found.
    """
    data = _load_all()
    record = data.get(approval_id)
    if record is None:
        return None

    if record["status"] != "pending":
        return ApprovalRequest(**record)  # already resolved -- no-op

    if submitted_code.strip().upper() == record["code"]:
        record["status"] = "approved"
    else:
        record["status"] = "rejected"

    _save_all(data)
    return ApprovalRequest(**record)


def mark_executed(approval_id: str) -> None:
    data = _load_all()
    if approval_id in data:
        data[approval_id]["status"] = "executed"
        _save_all(data)
