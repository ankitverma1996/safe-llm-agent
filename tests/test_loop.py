import os
import tempfile

import pytest


@pytest.fixture(autouse=True)
def isolated_approvals_file(monkeypatch):
    """Give each test its own approvals file so tests don't interfere."""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.remove(path)  # start with no file, matching a fresh boot
    monkeypatch.setenv("APPROVALS_FILE", path)

    # approvals.py reads the env var at import time, so reload it fresh
    import importlib
    import agent.approvals as approvals_module
    import agent.loop as loop_module

    importlib.reload(approvals_module)
    importlib.reload(loop_module)

    yield

    if os.path.exists(path):
        os.remove(path)


def test_read_tier_executes_immediately():
    from agent.loop import call_tool

    result = call_tool("list_pending_payments")
    assert "W1" in result


def test_mutation_tier_requires_approval():
    from agent.loop import call_tool

    result = call_tool("update_worker_note", worker_id="W1", note="test note")
    assert result["status"] == "pending_approval"
    assert result["tier"] == "mutation"
    assert "approval_id" in result and "approval_code" in result


def test_mutation_executes_after_correct_code():
    from agent.loop import call_tool, approve

    result = call_tool("update_worker_note", worker_id="W1", note="test note")
    outcome = approve(result["approval_id"], result["approval_code"])
    assert outcome["status"] == "executed"
    assert outcome["result"]["updated"] == "W1"


def test_wrong_code_does_not_execute():
    from agent.loop import call_tool, approve

    result = call_tool("send_payment", worker_id="W1", amount=5000)
    outcome = approve(result["approval_id"], "TOTALLYWRONG")
    assert outcome["status"] == "rejected"
    assert "did not match" in outcome["message"]


def test_money_tier_requires_approval_and_serializes():
    from agent.loop import call_tool, approve
    from agent.tools import Tier, TOOL_REGISTRY

    assert TOOL_REGISTRY["send_payment"].tier == Tier.MONEY

    result = call_tool("send_payment", worker_id="W1", amount=5000)
    assert result["status"] == "pending_approval"
    assert result["tier"] == "money"

    outcome = approve(result["approval_id"], result["approval_code"])
    assert outcome["status"] == "executed"
    assert outcome["result"]["status"] == "confirmed"


def test_model_cannot_bypass_tier_via_call_tool():
    # There is no parameter on call_tool that lets a caller mark an
    # action as pre-approved or skip the tier check -- tier is looked
    # up from the registry, not passed in by the caller.
    from agent.loop import call_tool
    import inspect

    sig = inspect.signature(call_tool)
    assert "tier" not in sig.parameters
    assert "skip_approval" not in sig.parameters
