"""Orka + LangChain — Full observability for your LangChain agents

Every LLM call, tool use, and chain step is automatically logged to your
Orka dashboard. No code changes to your existing chain logic required.

Requirements:
    pip install "orkaia[langchain]" langchain-openai

Run:
    ORKA_API_KEY=orka_... OPENAI_API_KEY=sk-... ORKA_AGENT_ID=... python langchain_example.py
"""
import os
import orka
from orka.integrations.langchain import OrkaCallbackHandler

orka.init(api_key=os.environ["ORKA_API_KEY"])
AGENT_ID = os.environ.get("ORKA_AGENT_ID", "replace-with-your-agent-id")

# ── Option A: Attach callback to LLM ─────────────────────────────────────────
# Every LLM call is logged to Orka
try:
    from langchain_openai import ChatOpenAI

    cb = OrkaCallbackHandler(agent_id=AGENT_ID)
    llm = ChatOpenAI(model="gpt-4o-mini", callbacks=[cb])

    print("Running LangChain with Orka observability...")
    response = llm.invoke("Explain what an AI agent is in one sentence.")
    print(f"Response: {response.content}")
    print("→ Check https://orka.ia.br/dashboard/executions to see all logged events\n")

except ImportError:
    print("Install langchain-openai: pip install langchain-openai")


# ── Option B: @orka.guard around your chain ───────────────────────────────────
# Wrap the entire chain call — policy check before + audit log after
@orka.guard(agent_id=AGENT_ID, task_type="langchain_chain", risk="MINIMAL")
def run_chain(user_input: str) -> str:
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage
        lm = ChatOpenAI(model="gpt-4o-mini")
        return lm.invoke([HumanMessage(content=user_input)]).content
    except ImportError:
        return f"[mock] Processed: {user_input[:50]}"


print("Running guarded chain...")
result = run_chain("What are the main risks of autonomous AI agents?")
print(f"Result: {result[:200]}...")
print("→ The entire chain execution is logged as a single auditable entry")
