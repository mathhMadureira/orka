# orkaia-js

TypeScript/JavaScript SDK for [Orka](https://orka.ia.br) — observability and policy control for AI agents.

```bash
npm install orkaia-js
```

## Quickstart

```typescript
import orka from "orkaia-js";

orka.init("orka_your_key_here");

const summarize = orka.guard(
  async (text: string) => yourLlm.call(text),
  { agentId: "my-agent", taskType: "summarize" }
);

const result = await summarize("some input");
```

Every call to the wrapped function:
1. Checks active policies for `agentId` + `taskType` before running
2. Runs your function unchanged
3. Logs input, output, duration, and status to your Orka dashboard

## Handling policy blocks

```typescript
import orka, { OrkaPolicyBlocked } from "orkaia-js";

orka.init("orka_...");

const sendEmail = orka.guard(
  async (to: string, body: string) => emailClient.send(to, body),
  { agentId: "my-agent", taskType: "send_email", blockOnPolicy: true }
);

try {
  await sendEmail("user@example.com", "...");
} catch (e) {
  if (e instanceof OrkaPolicyBlocked) {
    console.log(`Blocked: ${e.policyName} — ${e.reason}`);
  }
}
```

## Exceptions

| Exception | When raised |
|---|---|
| `OrkaPolicyBlocked` | A policy blocked the call |
| `OrkaAuthError` | Invalid or expired API key |
| `OrkaConnectionError` | Cannot reach the Orka backend |

## License

MIT
