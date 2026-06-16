# Orka Python SDK

**Observability and control for AI agents in production.**

Add one decorator to any agent function and instantly see every action, cost, and error in real time — with the ability to pause and require human approval before destructive operations.

```bash
pip install orkaia
```

[![PyPI version](https://img.shields.io/pypi/v/orkaia.svg)](https://pypi.org/project/orkaia/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Works with LangChain](https://img.shields.io/badge/LangChain-compatible-green.svg)](https://python.langchain.com/)
[![Works with CrewAI](https://img.shields.io/badge/CrewAI-compatible-green.svg)](https://crewai.com/)
[![Works with AutoGen](https://img.shields.io/badge/AutoGen-compatible-green.svg)](https://microsoft.github.io/autogen/)

---

## The problem

You deploy an AI agent. It runs. You have no idea what it's actually doing.

- Did it make the right API calls?
- Why did it fail on that one input?
- What did it spend your money on at 3am?
- Did it hit a rate limit or get blocked by a policy?

Logs don't capture the full chain. Debugging is a detective game. You limit your agent's capabilities out of fear rather than trust.

**Orka fixes that.** Connect once. See everything.

---

## Quickstart (5 minutes)

**1. Install**
```bash
pip install orkaia
```

**2. Initialize**
```python
import orka

orka.init(api_key="orka_your_key_here")
# Get your key at https://orka.ia.br → Settings → API Keys
```

**3. Add to your agent**
```python
@orka.guard(agent_id="my-agent", task_type="summarize")
def run_agent(text: str) -> str:
    return your_llm.call(text)  # your existing code, unchanged
```

**4. Open the dashboard**

Every execution appears in real time at [orka.ia.br/dashboard](https://orka.ia.br/dashboard):
- Input and output of every call
- Duration and estimated cost
- Status: COMPLETED / FAILED / BLOCKED / WAITING_APPROVAL
- Risk score per execution
- Full audit trail, searchable and exportable

---

## How `@orka.guard` works

```python
@orka.guard(
    agent_id="my-agent",   # identifies which agent this function belongs to
    task_type="summarize", # categorizes the action for policy matching
    risk="MINIMAL",        # MINIMAL | LIMITED | HIGH | UNACCEPTABLE
    block_on_policy=True,  # raise OrkaPolicyBlocked if a policy denies it
)
def run_agent(text: str) -> str:
    return llm.call(text)
```

What happens on every call:
1. **Policy check** → Orka evaluates active policies for this agent+task_type
2. **Your function runs** → exactly as before, no changes to your logic
3. **Execution logged** → input, output, duration, status sent to Orka
4. **Risk scored** → automatic risk assessment stored on the execution record

Works with both `def` and `async def` — detected automatically.

---

## LangChain integration

```bash
pip install "orkaia[langchain]" langchain-openai
```

```python
import orka
from orka.integrations.langchain import OrkaCallbackHandler
from langchain_openai import ChatOpenAI

orka.init(api_key="orka_...")

# Every LLM call, tool use, and chain step logged to Orka automatically
cb  = OrkaCallbackHandler(agent_id="my-agent")
llm = ChatOpenAI(model="gpt-4o", callbacks=[cb])

response = llm.invoke("Summarize this document...")
# → See the full call trace in your Orka dashboard
```

Or use `@orka.guard` around your entire chain for a single auditable entry:

```python
@orka.guard(agent_id="my-agent", task_type="langchain_chain")
def run_chain(user_input: str) -> str:
    chain = prompt | llm | output_parser
    return chain.invoke({"input": user_input})
```

---

## CrewAI integration

```bash
pip install orkaia crewai
```

```python
import orka

orka.init(api_key="orka_...")

@orka.guard(agent_id="researcher", task_type="web_search", risk="MINIMAL")
def search_web(query: str) -> str:
    return firecrawl.scrape(query)

@orka.guard(agent_id="analyst", task_type="data_analysis", risk="LIMITED")
def analyze_data(data: dict) -> str:
    return llm.analyze(data)

# Wrap any tool — the rest of your CrewAI code is unchanged
```

---

## OpenAI integration

```bash
pip install "orkaia[openai]" openai
```

```python
import orka
from orka.integrations.openai import OrkaOpenAIAdapter
from openai import OpenAI

orka.init(api_key="orka_...")

adapter = OrkaOpenAIAdapter(openai_client=OpenAI(), agent_id="my-agent")
response = adapter.run("List my agents and run a summarization task")
# → Orka tool calls handled automatically in the loop
```

---

## Resource API

Full programmatic control over agents and executions:

```python
from orka import OrkaClient

client = OrkaClient(api_key="orka_...")

# Manage agents
agent = client.agents.create(
    name="my-agent",
    endpoint_url="https://my-agent.example.com/run",
    trust_level="MEDIUM",
)

# Query executions
executions = client.executions.list(agent_id=agent["id"], limit=20)
for ex in executions:
    print(ex["id"], ex["status"], ex["task_type"], ex["duration_ms"])

# Agent-to-agent delegation (X-Handover)
task = client.handover.request(
    from_agent_id="orchestrator-id",
    to_agent_id="specialist-id",
    task_type="deep_analysis",
    payload={"data": "..."},
)
```

---

## Policies and approval flows

Block or pause actions based on risk level, task type, or custom rules — configured in the dashboard, enforced in code.

```python
@orka.guard(
    agent_id="my-agent",
    task_type="send_email",
    risk="HIGH",
    block_on_policy=True,
)
def send_email(to: str, subject: str, body: str) -> bool:
    return email_client.send(to, subject, body)

try:
    send_email("user@example.com", "Report", "...")
except orka.OrkaPolicyBlocked as e:
    print(f"Blocked: {e.policy_name} — {e.reason}")
    # The request is queued in Orka's approval flow
    # Approve or reject from https://orka.ia.br/dashboard/approvals
```

---

## Exceptions

| Exception | When raised |
|---|---|
| `orka.OrkaPolicyBlocked` | A policy blocked the execution |
| `orka.OrkaAuthError` | Invalid or expired API key |
| `orka.OrkaConnectionError` | Cannot reach Orka backend |

---

## Why Orka vs. LangSmith / Langfuse / AgentOps

|                        | Orka | LangSmith | Langfuse | AgentOps |
|------------------------|------|-----------|----------|----------|
| Works with any framework | ✓  | LangChain only | ✓ | ✓ |
| Policy-based blocking  | ✓    | ✗ | ✗ | ✗ |
| Human approval flow    | ✓    | ✗ | ✗ | ✗ |
| Free tier              | 10k exec/mo | 5k traces/mo | Self-hosted | — |
| One-decorator setup    | ✓    | ✓ | ✓ | ✓ |

Orka is the only observability tool that gives you **active control** — pause an agent, require human approval before a destructive action, and enforce policies that block bad behavior before it happens.

---

## Installation options

```bash
pip install orkaia                  # core
pip install "orkaia[langchain]"     # + LangChain callback handler
pip install "orkaia[openai]"        # + OpenAI adapter
pip install "orkaia[all]"           # everything
```

Requires Python 3.10+.

---

## Examples

See [`examples/`](examples/) for ready-to-run scripts:

| File | What it shows |
|------|---------------|
| [`quickstart.py`](examples/quickstart.py) | Minimal setup in 30 lines |
| [`langchain_example.py`](examples/langchain_example.py) | LangChain callback handler |
| [`openai_example.py`](examples/openai_example.py) | OpenAI function calling loop |
| [`crewai_example.py`](examples/crewai_example.py) | CrewAI tool wrapping |

---

## Links

- **Dashboard**: [orka.ia.br](https://orka.ia.br)
- **Documentation**: [orka.ia.br/docs](https://orka.ia.br/docs)
- **Issues**: [GitHub Issues](https://github.com/orka-runtime/orka-sdk/issues)

---

MIT License © [Orka](https://orka.ia.br)
