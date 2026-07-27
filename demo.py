"""
Interactive CLI demo of the tiered-permission agent pattern.

Simulates what would normally happen over Microsoft Teams / Slack:
the model calls tools, read actions execute immediately, and
mutation/money actions pause for a human to type the approval code.

Run:
    python demo.py
"""

from agent.loop import call_tool, approve


def main():
    print("=== Safe LLM Agent Demo ===\n")

    print("1) READ-tier call (executes immediately):")
    print(call_tool("list_pending_payments"))
    print()

    print("2) MUTATION-tier call (requires approval):")
    result = call_tool("update_worker_note", worker_id="W1", note="Contacted re: bank details")
    print(result)
    approval_id = result["approval_id"]
    code = result["approval_code"]
    print()

    print("   Simulating human approving with the correct code...")
    print(approve(approval_id, code))
    print()

    print("3) MONEY-tier call (requires approval, serialized execution):")
    result = call_tool("send_payment", worker_id="W1", amount=5000)
    print(result)
    approval_id = result["approval_id"]
    code = result["approval_code"]
    print()

    print("   Simulating a WRONG code first...")
    print(approve(approval_id, "WRONGCODE"))
    print()

    print("   (Wrong code rejects the request -- it does not execute.)")
    print("   Real approval codes are single-use; requesting the action again:")
    result = call_tool("send_payment", worker_id="W1", amount=5000)
    approval_id = result["approval_id"]
    code = result["approval_code"]
    print(approve(approval_id, code))


if __name__ == "__main__":
    main()
