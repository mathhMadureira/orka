<div align="center">

<img src="https://orka.ia.br/icon.svg" width="64" height="64" alt="ORKA" />

# ORKA

**Governance and audit layer for AI agents.**

AI agents take actions without oversight.  
ORKA gives you control, approval flows, and immutable audit trails.

[![Beta](https://img.shields.io/badge/status-beta-5B5FFF?style=flat-square)](https://orka.ia.br)
[![Platform](https://img.shields.io/badge/platform-web-black?style=flat-square)](https://orka.ia.br)
[![Protocol](https://img.shields.io/badge/supports-MCP%20%7C%20A2A%20%7C%20REST-22C55E?style=flat-square)](#)

[**Request Beta Access →**](https://orka.ia.br/register)

</div>

---

## The problem

AI agents are increasingly autonomous — they browse the web, write emails, execute code, call APIs, and transfer data.

But most teams have **no visibility** into what their agents are actually doing.

- No approval flow before a risky action
- No audit trail after something goes wrong
- No policy enforcement across multiple agents
- No way to quantify risk per agent

ORKA solves this.

---

## What ORKA does

ORKA sits between your AI agents and the outside world. Every action goes through a control layer before execution.

```
Agent  →  ORKA  →  Policy check  →  Risk analysis  →  [Human approval?]  →  Execute  →  Immutable ledger
```

**Every step is logged. Nothing is irreversible without consent.**

---

## Features

| Feature | Description |
|---|---|
| **X-Shield** | Policy engine — define rules per agent, domain, or task type |
| **Approval flows** | Require human sign-off before high-risk actions execute |
| **X-Assurance** | Dynamic risk scoring per agent based on execution history |
| **Immutable ledger** | Cryptographically chained audit trail — tamper-evident by design |
| **Multi-protocol** | Supports MCP, A2A, REST, and custom agent protocols |
| **Real-time dashboard** | Live overview of all agents, executions, blocks, and alerts |

---

## How it works

### 1. Register your agent

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

### 2. Route actions through ORKA

Instead of calling external services directly, your agent sends a handover request:

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

### 3. ORKA enforces your policies

If the action triggers a policy rule (e.g. amount > $200 requires approval), ORKA:

- **Blocks** the action automatically, or
- **Pauses** and requests human approval, then
- **Logs** the full event to the immutable ledger

### 4. You see everything

Every action, decision, approval, and block is visible in the dashboard in real time.

---

## Example scenario

> **Agent:** "Approve a $1,200 refund for customer #4821"

| Step | What happens |
|---|---|
| Agent sends request | ORKA receives the handover |
| Policy check | Rule: refunds > $500 require approval |
| Risk analysis | Score: 72/100 — flagged as HIGH |
| Human approval | Notification sent to the team |
| Approved | Action executes |
| Ledger entry | Immutable record created with full context |

Without ORKA, this refund would execute instantly with no record.

---

## Dashboard

Live control panel with real-time metrics, execution history, risk scores, and audit trail.

> **→ [See it live at orka.ia.br](https://orka.ia.br)**  
> Beta access is free. Request an account to connect your first agent.

---

## API reference

Base URL: `https://orka.ia.br/api/v1`

| Endpoint | Method | Description |
|---|---|---|
| `/agents/` | GET / POST | List or register agents |
| `/handover` | POST | Submit an action for ORKA to process |
| `/handover/{task_id}` | GET | Check execution status |
| `/xshield/policies` | GET / POST | Manage governance policies |
| `/approvals` | GET | List pending human approvals |
| `/approvals/{id}/approve` | POST | Approve a pending action |
| `/xledger/entries` | GET | Query the immutable audit ledger |
| `/xledger/verify` | GET | Verify chain integrity |
| `/assurance/risk-report` | GET | Per-agent risk scores and insurance model |
| `/metrics/dashboard` | GET | Real-time platform metrics |

Authentication: `X-API-Key` header or `Bearer` token (issued per agent via `/xshield/tokens`).

---

## Beta access

ORKA is currently in **private beta**.

- Free to use during beta
- No credit card required
- Priority support via email

**[Register at orka.ia.br →](https://orka.ia.br/register)**

Or email: **orkaruntimesuporte@hotmail.com**

---

## Tech stack

- **Backend:** FastAPI (Python) — hosted on Render
- **Frontend:** Next.js 16 — hosted on Vercel
- **Database:** PostgreSQL
- **Audit ledger:** SHA-256 chained entries, verified on read
- **Agent protocols:** MCP, A2A, REST, Custom

---

<div align="center">

Built for teams that deploy AI agents and need to stay in control.

**[orka.ia.br](https://orka.ia.br)**

</div>
