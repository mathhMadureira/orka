Show HN: Orka -- Stop your AI agents from burning money on runaway loops

Link: https://github.com/mathhMadureira/orka

We built this after our own agent looped on a failed API call and burned $200 over a weekend while we slept.

Orka is an operational control layer for AI agents. It sits between your agent and the world:

- Loop guard -- detects repeated failed actions and cuts them before draining budget
- Spend cap -- hard token/cost limit per run
- Human approval -- holds high-risk actions for sign-off
- Immutable audit trail -- SHA-256 chained ledger, tamper-evident
- Savings ledger -- quantifies in dollars what it prevented

SDK is MIT (Python + TypeScript). Backend is managed at orka.ia.br.

One decorator:

    @orka.guard(agent_id="finance", task_type="transfer", risk="HIGH")
    def my_agent(task): ...

Works with LangChain, CrewAI, AutoGen, OpenAI, MCP.

Try the 10-second demo: github.com/mathhMadureira/orka/tree/main/examples/runaway-loop-demo

Would love feedback from anyone running agents in production.
