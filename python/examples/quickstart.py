"""Orka SDK — Quickstart

This example shows the two main ways to use Orka:
  1. @orka.guard decorator (recommended for most use cases)
  2. OrkaClient resource API (for full control)

Requirements:
    pip install orkaia

Setup:
    1. Create an account at https://orka.ia.br
    2. Go to Settings → API Keys → Create Key
    3. Set ORKA_API_KEY=orka_... in your environment

Run:
    ORKA_API_KEY=orka_... python quickstart.py
"""
import os
import time

import orka

# ── 1. Initialize ─────────────────────────────────────────────────────────────
api_key = os.environ.get("ORKA_API_KEY", "orka_your_key_here")
client = orka.init(api_key=api_key)

print("✓ Orka initialized")
print(f"  Dashboard: https://orka.ia.br/dashboard\n")


# ── 2. Decorator pattern (simplest) ───────────────────────────────────────────
# Replace "your-agent-id" with a real agent ID from your dashboard
AGENT_ID = os.environ.get("ORKA_AGENT_ID", "replace-with-your-agent-id")


@orka.guard(agent_id=AGENT_ID, task_type="summarize", risk="MINIMAL")
def summarize(text: str) -> str:
    """Mock agent: every call is logged to Orka automatically."""
    # In production, this would call your LLM or agent logic
    words = text.split()[:10]
    return f"Summary: {' '.join(words)}..."


# Run the guarded function — Orka logs this execution
print("Running guarded function...")
result = summarize("The quick brown fox jumps over the lazy dog " * 5)
print(f"  Result: {result}")
print("  → Check your dashboard to see the execution log\n")


# ── 3. Resource API (full control) ────────────────────────────────────────────
print("Listing agents via resource API...")
try:
    agents = client.agents.list()
    print(f"  Found {len(agents)} agent(s)")
    for agent in agents[:3]:
        print(f"  - {agent['name']} (id: {agent['id']}, trust: {agent.get('trust_level', 'N/A')})")
except orka.OrkaAuthError:
    print("  ✗ Authentication failed — check your ORKA_API_KEY")
except orka.OrkaConnectionError:
    print("  ✗ Cannot connect to Orka backend — is the server running?")

print("\n✓ Done! Open https://orka.ia.br/dashboard to see the execution.")
