"""
The core safety pattern: an agent that can propose actions, but can
never itself decide that a mutation/money-tier action is authorized.

- READ tier tools execute immediately -- no side effects, so no gate needed.
- MUTATION and MONEY tier tools always create a pending approval instead
  of executing directly. A human must call `approve()` with the correct
  code before `execute_if_approved()` will actually run the tool.
- MONEY tier additionally uses a lock so at most one money-moving action
  can be approved-and-executing at any time, preventing two concurrent
  payments from racing each other.
"""

import threading
from typing import Optional

from agent.approvals import ApprovalRequest, create_approval, resolve, mark_executed
from agent.tools import TOOL_REGISTRY, Tier

_money_lock = threading.Lock()


def call_tool(tool_name: str, **kwargs) -> dict:
    """
    Entry point the model uses to call a tool. This is the ONLY path
    into tool execution -- there is no direct way for the model to
    bypass the tier check.
    """
    tool = TOOL_REGISTRY.get(tool_name)
    if tool is None:
        return {"error": f"unknown tool: {tool_name}"}

    if tool.tier == Tier.READ:
        return tool.handler(**kwargs)

    # MUTATION or MONEY: never execute directly. Create a pending
    # approval and tell the caller (and, in a real system, the human
    # via Teams/Slack/etc) that this action needs sign-off.
    request = create_approval(tool_name=tool_name, args=kwargs, tier=tool.tier.value)
    return {
        "status": "pending_approval",
        "approval_id": request.id,
        "tier": request.tier,
        "approval_code": request.code,  # in production this goes to
                                          # the approver's channel, not
                                          # back to the model
        "message": (
            f"'{tool_name}' is a {tool.tier.value}-tier action and requires "
            f"human approval. Reply with the approval code to confirm."
        ),
    }


def approve(approval_id: str, code: str) -> dict:
    """Human-facing: submit the approval code for a pending action."""
    resolved = resolve(approval_id, code)
    if resolved is None:
        return {"error": "no such approval request"}
    if resolved.status != "approved":
        return {"status": resolved.status, "message": "code did not match"}

    return execute_if_approved(resolved)


def execute_if_approved(request: ApprovalRequest) -> dict:
    if request.status != "approved":
        return {"error": "not approved", "status": request.status}

    tool = TOOL_REGISTRY[request.tool_name]

    if tool.tier == Tier.MONEY:
        # Serialize all money-tier execution so two approved payments
        # can never run concurrently and race each other.
        with _money_lock:
            result = tool.handler(**request.args)
    else:
        result = tool.handler(**request.args)

    mark_executed(request.id)
    return {"status": "executed", "result": result}
