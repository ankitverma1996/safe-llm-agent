"""
Tool definitions and tier classification.

Every tool an agent can call is classified into one of three tiers:

  READ     -- no side effects, executes immediately
  MUTATION -- changes data, requires human approval before executing
  MONEY    -- moves money, requires human approval AND is serialized
              (only one money-tier action can be in flight at a time)

The tier is a property of the *tool*, not something the model decides
at call time -- this is the core safety property: the model can never
grant itself elevated permission by simply claiming a mutation is safe.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict


class Tier(str, Enum):
    READ = "read"
    MUTATION = "mutation"
    MONEY = "money"


@dataclass
class Tool:
    name: str
    description: str
    tier: Tier
    handler: Callable[..., dict]


# --- Example handlers -------------------------------------------------
# In a real system these would call actual services (a database, a
# payments API, etc). Here they're simple in-memory stand-ins so the
# whole project is runnable with no external dependencies.

_FAKE_DB = {
    "W1": {"name": "Ankit", "pending_payment": 5000},
    "W2": {"name": "Priya", "pending_payment": 3200},
}


def _list_pending_payments(**kwargs) -> dict:
    return {w: v["pending_payment"] for w, v in _FAKE_DB.items()}


def _update_worker_note(worker_id: str, note: str, **kwargs) -> dict:
    if worker_id not in _FAKE_DB:
        return {"error": f"unknown worker {worker_id}"}
    _FAKE_DB[worker_id]["note"] = note
    return {"updated": worker_id, "note": note}


def _send_payment(worker_id: str, amount: float, **kwargs) -> dict:
    if worker_id not in _FAKE_DB:
        return {"error": f"unknown worker {worker_id}"}
    _FAKE_DB[worker_id]["pending_payment"] = 0
    return {"sent": worker_id, "amount": amount, "status": "confirmed"}


TOOL_REGISTRY: Dict[str, Tool] = {
    "list_pending_payments": Tool(
        name="list_pending_payments",
        description="List all workers with a pending payment amount.",
        tier=Tier.READ,
        handler=_list_pending_payments,
    ),
    "update_worker_note": Tool(
        name="update_worker_note",
        description="Attach an internal note to a worker's record.",
        tier=Tier.MUTATION,
        handler=_update_worker_note,
    ),
    "send_payment": Tool(
        name="send_payment",
        description="Send a real payment to a worker. Moves real money.",
        tier=Tier.MONEY,
        handler=_send_payment,
    ),
}
