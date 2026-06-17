<p align="center">
  <img src="https://orka.ia.br/icon.svg" alt="ORKA" width="96" />
</p>

# ORKA

**Observability and policy control for AI agents in production.**

AI agents take actions without oversight — they spend money, send emails, write to databases, and call APIs with no human checkpoint. ORKA adds that checkpoint.

> **What's open and what's not:** the Python and TypeScript SDKs in this repo are open source (MIT) — read them, fork them, run them. The governance backend they talk to (policy engine, risk scoring, immutable ledger) is a proprietary managed service at [orka.ia.br](https://orka.ia.br). This is an open-core project, not a self-hostable platform — see [Contributing](#contributing) for the exact line.

[![PyPI version](https://img.shields.io/pypi/v/orkaia.svg)](https://pypi.org/project/orkaia/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/mathhMadureira/orka/blob/main/LICENSE) [![Protocol](https://img.shields.io/badge/supports-MCP%20%7C%20A2A%20%7C%20REST-22C55E?style=flat-square)](#)

[**orka.ia.br →**](https://orka.ia.br)

---

## The problem

Real incidents, not hypotheticals:

- An OpenAI Operator agent bought a dozen eggs for $31 without asking — its own safety protocol failed to trigger.
- Replit's coding agent deleted a production database in 9 seconds, during a code freeze meant to prevent exactly that.
- Air Canada was held legally liable for a refund policy its chatbot invented on the spot.

Most teams running AI agents have **no checkpoint** between the agent's decision and the irreversible action — no approval flow, no audit trail, no policy enforcement, no way to quantify risk per agent.

ORKA sits between your agent and the outside world:

```
Agent  →  ORKA  →  Policy check  →  Risk score  →  [Human approval?]  →  Execute  →  Immutable ledger
```

Every step is logged. Nothing irreversible happens without consent.

---

## How it's split

| Layer | What it is | Where it lives |
| --- | --- | --- |
| **Client SDKs** (`python/`, `typescript/`) | The `@guard` decorator, the REST client, examples, integrations | This repo, MIT, runs on your side |
| **Governance backend** | Policy engine, risk scoring, immutable ledger, approval routing | Proprietary, managed service at orka.ia.br |

The SDK is a thin client: it intercepts the call and hands it to the backend. The decision logic runs server-side. If you need everything in your own infrastructure, ORKA isn't that today — and the SDK code here lets you see exactly what crosses the boundary before you trust it.

---

## Quickstart

You'll need an API key from [orka.ia.br](https://orka.ia.br) → Settings → API Keys (this is what connects the SDK to the managed backend).

**Python**

```bash
pip install orkaia
```

```python
import orka

orka.init(api_key="orka_your_key_here")

@orka.guard(agent_id="my-agent", task_type="summarize")
def run_agent(text: str) -> str:
    return your_llm.call(text)  # unchanged
```

Full SDK, integrations (LangChain, CrewAI, OpenAI), and examples: [`python/`](https://github.com/mathhMadureira/orka/blob/main/python)

**TypeScript / JavaScript**

```bash
npm install orkaia-js
```

```typescript
import orka from "orkaia-js";

orka.init("orka_your_key_here");

const summarize = orka.guard(
  async (text: string) => yourLlm.call(text),
  { agentId: "my-agent", taskType: "summarize" }
);
```

Full SDK: [`typescript/`](https://github.com/mathhMadureira/orka/blob/main/typescript)

Every execution appears in real time at [orka.ia.br/dashboard](https://orka.ia.br/dashboard): input/output, duration, status, risk score, and a searchable audit trail.

---

## Features

| Feature | Description |
| --- | --- |
| **X-Shield** | Policy engine — rules per agent, domain, or task type |
| **Approval flows** | Require human sign-off before high-risk actions execute |
| **X-Assurance** | Dynamic risk scoring per agent based on execution history |
| **Immutable ledger** | SHA-256 chained audit trail — tamper-evident by design |
| **Multi-protocol** | MCP, A2A, REST, and custom agent protocols |
| **Zapier connector** | Add a human-approval step to any Zap, no code required |

---

## How it works without the SDK (REST)

**1. Register your agent**

```bash
curl -X POST https://orka.ia.br/api/v1/agents/ \
  -H "X-API-Key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-agent",
    "protocol": "REST",
    "domain": "finance",
    "endpoint_url": "https://my-agent.example.com",
    "capabilities": ["data_analysis", "report_generation"]
  }'
```

**2. Route actions through ORKA**

```bash
curl -X POST https://orka.ia.br/api/v1/handover \
  -H "Authorization: Bearer agent_token" \
  -H "Content-Type: application/json" \
  -d '{
    "requesting_agent_id": "agent_id",
    "executing_agent_target": "payment-processor",
    "task_type": "process_refund",
    "task_payload": { "amount": 500, "customer_id": "cust_123" }
  }'
```

**3. ORKA enforces your policies** — blocks automatically, or pauses for human approval, then logs the full event to the immutable ledger regardless of outcome.

---

## Example scenario

> **Agent:** "Approve a $1,200 refund for customer #4821"

| Step | What happens |
| --- | --- |
| Agent sends request | ORKA receives the handover |
| Policy check | Rule: refunds > $500 require approval |
| Risk analysis | Score: 72/100 — flagged as HIGH |
| Human approval | Notification sent to the team |
| Approved | Action executes |
| Ledger entry | Immutable record created with full context |

Without ORKA, this refund executes instantly with no record.

---

## Dashboard

![ORKA Dashboard Overview](https://github.com/mathhMadureira/orka/raw/main/dashboard-overview.png)
![ORKA Dashboard Full](https://github.com/mathhMadureira/orka/raw/main/dashboard.png)

---

## API reference

Base URL: `https://orka.ia.br/api/v1`

| Endpoint | Method | Description |
| --- | --- | --- |
| `/agents/` | GET / POST | List or register agents |
| `/handover` | POST | Submit an action for ORKA to process |
| `/handover/{task_id}` | GET | Check execution status |
| `/xshield/policies` | GET / POST | Manage governance policies |
| `/approvals` | GET | List pending human approvals |
| `/approvals/{id}/approve` | POST | Approve a pending action |
| `/xledger/entries` | GET | Query the immutable audit ledger |
| `/xledger/verify` | GET | Verify chain integrity |
| `/assurance/risk-report` | GET | Per-agent risk scores |
| `/metrics/dashboard` | GET | Real-time platform metrics |

Authentication: `X-API-Key` header, or a `Bearer` agent token issued via `/xshield/tokens`.

---

## Tech stack

- **Backend:** FastAPI (Python) — proprietary, managed service
- **Frontend:** Next.js
- **Database:** PostgreSQL with row-level security
- **Audit ledger:** SHA-256 chained entries
- **Agent protocols:** MCP, A2A, REST, custom

---

## Contributing

ORKA is **open-core**:

- The client SDKs in [`python/`](https://github.com/mathhMadureira/orka/blob/main/python) and [`typescript/`](https://github.com/mathhMadureira/orka/blob/main/typescript) are MIT-licensed and fully open — read, fork, improve.
- The governance backend (policy engine, risk scoring, ledger) is proprietary and runs as a managed service. It is **not** in this repo and is not self-hostable today.

Issues and PRs on the SDKs are welcome. If self-hosting the backend is a hard requirement for you, open an issue and say so — that's exactly the kind of signal that decides the roadmap.

---

Built for teams that deploy AI agents and need to stay in control.

**[orka.ia.br](https://orka.ia.br)** · contato@orka.ia.br
