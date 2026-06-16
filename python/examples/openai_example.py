"""Orka + OpenAI — Observability for OpenAI function calling agents

Use @orka.guard to audit any function your agent calls, or use OrkaOpenAIAdapter
for a higher-level chat loop with automatic Orka tool handling.

Requirements:
    pip install "orkaia[openai]" openai

Run:
    ORKA_API_KEY=orka_... OPENAI_API_KEY=sk-... ORKA_AGENT_ID=... python openai_example.py
"""
import os
import orka

orka.init(api_key=os.environ["ORKA_API_KEY"])
AGENT_ID = os.environ.get("ORKA_AGENT_ID", "replace-with-your-agent-id")


# ── Option A: @orka.guard on any OpenAI-powered function ─────────────────────
@orka.guard(agent_id=AGENT_ID, task_type="openai_call", risk="MINIMAL")
def call_openai(prompt: str) -> str:
    try:
        from openai import OpenAI
        client = OpenAI()
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        return r.choices[0].message.content or ""
    except ImportError:
        return f"[mock] Response to: {prompt[:50]}"


print("Running guarded OpenAI call...")
result = call_openai("List three benefits of AI agent observability.")
print(f"Result:\n{result}\n")
print("→ Check https://orka.ia.br/dashboard/executions\n")


# ── Option B: OrkaOpenAIAdapter for a full agent loop ─────────────────────────
# The adapter handles tool calls to Orka automatically (list agents, run executions)
try:
    from openai import OpenAI
    from orka.integrations.openai import OrkaOpenAIAdapter

    adapter = OrkaOpenAIAdapter(
        openai_client=OpenAI(),
        agent_id=AGENT_ID,
        model="gpt-4o-mini",
    )

    print("Running OpenAI adapter (tool-calling loop)...")
    response = adapter.run("List my registered Orka agents and tell me how many there are.")
    print(f"Response: {response}")

except ImportError:
    print("Install openai: pip install openai")
except orka.OrkaAuthError:
    print("✗ Auth failed — check ORKA_API_KEY")
