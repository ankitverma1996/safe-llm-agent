# Safe LLM Agent — Tiered Tool Permissions

[![Tests](https://github.com/ankitverma1996/safe-llm-agent/actions/workflows/tests.yml/badge.svg)](https://github.com/ankitverma1996/safe-llm-agent/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A small, runnable demo of a safety pattern for LLM agents that can take
real actions: **the model can propose an action, but it can never be
the thing that authorizes it.**

This is a generalized, non-proprietary version of a pattern I use in a
production Teams-based agent that lets ops staff query and act on
payroll data conversationally — including triggering real payments.

## The core idea

Every tool an agent can call is classified into a tier **at
registration time**, not decided by the model at call time:

| Tier | Behavior |
|---|---|
| `READ` | No side effects. Executes immediately. |
| `MUTATION` | Changes data. Requires a human to approve with a code before it runs. |
| `MONEY` | Moves money. Requires approval **and** executes under a lock, so at most one money-moving action can be in flight at a time. |

The model has exactly one way to call a tool (`agent.loop.call_tool`),
and that function looks the tier up from a fixed registry — there is
no parameter the model (or a malicious prompt) can pass to skip the
approval gate or self-declare an action as safe.

## Why persistence matters

`agent/approvals.py` writes every approval request to disk **the
moment it's proposed** — before anything executes. This is what makes
the system safe across a restart: if the process crashes or restarts
while an approval is pending, it reloads the pending request from disk
and re-announces it, instead of either losing it silently or (much
worse) coming back up and treating an unconfirmed action as if it had
already been approved.

## Why the money lock matters

Two approved payments executing concurrently could race — e.g. reading
a stale "pending balance" and double-paying. `agent/loop.py` serializes
all `MONEY` tier execution behind a single lock so that can't happen.

## Project structure

```
agent/
  tools.py       # tool registry + tier classification
  approvals.py    # persisted approval request state
  loop.py         # the safety gate: call_tool() / approve()
tests/
  test_loop.py
demo.py           # interactive CLI walkthrough
```

## Running the demo

```bash
pip install -r requirements.txt
python demo.py
```

This simulates: a read call executing immediately, a mutation call
being approved with the correct code, a money call being *rejected*
with the wrong code, and then successfully executed with the right one.

## Running tests

```bash
pytest tests/ -v
```

Tests cover: read tier executing immediately, mutation/money tiers
requiring approval, wrong codes being rejected (not executed), and a
structural check that `call_tool()` has no parameter that could be
used to bypass the tier system.

## What's simplified vs. the production version

- No real LLM call — `demo.py` simulates what the model would trigger,
  so this repo is runnable standalone with no API key required.
- Approvals are resolved via direct function call instead of over a
  real channel like Microsoft Teams.
- The "database" is an in-memory dict instead of a real datastore.

The safety pattern itself — tier classification at registration time,
persisted pending state, and a lock around money-tier execution — is
the same shape as the production system.
