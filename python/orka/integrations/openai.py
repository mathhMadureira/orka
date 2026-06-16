"""OpenAI integration for Orka.

Install:
    pip install "orkaia[openai]"

Usage:
    import orka
    from orka.integrations.openai import OrkaOpenAIAdapter
    from openai import OpenAI

    orka.init(api_key="orka_...")
    openai_client = OpenAI()

    adapter = OrkaOpenAIAdapter(openai_client=openai_client, agent_id="my-agent")
    result = adapter.run("List my tasks and create a summary report")
    print(result)
"""
from __future__ import annotations

import json
import time
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from orka import OrkaClient


def orka_tools_schema() -> list[dict]:
    """Return Orka tools in OpenAI function-calling format.

    Pass the result directly to the `tools` parameter of chat.completions.create().
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "orka_execute",
                "description": (
                    "Execute a task through the Orka AI observability layer. "
                    "Every call is logged, policy-checked, and visible in your dashboard."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "Orka agent ID"},
                        "task_type": {"type": "string", "description": "Task type (e.g. 'summarize', 'translate')"},
                        "payload": {"type": "object", "description": "Task input payload"},
                    },
                    "required": ["agent_id", "task_type"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "orka_list_agents",
                "description": "List all AI agents registered in Orka for this organization.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "orka_get_execution",
                "description": "Get the status and output of an Orka execution.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "execution_id": {"type": "string"},
                    },
                    "required": ["execution_id"],
                },
            },
        },
    ]


def handle_orka_tool_call(
    tool_call: Any,
    client: "OrkaClient",
    *,
    poll_interval: float = 2.0,
    max_polls: int = 20,
) -> str:
    """Dispatch an OpenAI ToolCall to Orka and return the result as a JSON string."""
    if hasattr(tool_call, "function"):
        name = tool_call.function.name
        args = json.loads(tool_call.function.arguments or "{}")
    else:
        name = tool_call["function"]["name"]
        args = json.loads(tool_call["function"].get("arguments", "{}"))

    if name == "orka_list_agents":
        return json.dumps(client.agents.list())

    if name == "orka_get_execution":
        return json.dumps(client.executions.get(args["execution_id"]))

    if name == "orka_execute":
        execution = client.executions.create(
            agent_id=args["agent_id"],
            task_type=args["task_type"],
            payload=args.get("payload", {}),
        )
        execution_id = execution["id"]
        for _ in range(max_polls):
            time.sleep(poll_interval)
            result = client.executions.get(execution_id)
            status = result["status"]
            if status == "COMPLETED":
                return json.dumps(result.get("output_payload") or {"status": "completed"})
            if status == "WAITING_APPROVAL":
                return json.dumps({"status": "waiting_approval", "execution_id": execution_id})
            if status in ("FAILED", "BLOCKED", "TIMED_OUT"):
                return json.dumps({
                    "status": status,
                    "error": result.get("error_message"),
                    "execution_id": execution_id,
                })
        return json.dumps({"status": "timeout", "execution_id": execution_id})

    return json.dumps({"error": f"Unknown Orka tool: {name}"})


class OrkaOpenAIAdapter:
    """Wraps an OpenAI chat completion loop with automatic Orka tool handling.

    Every tool call the model makes is dispatched to Orka — all observability
    (logging, policy checks, approval flow) applies transparently.

    Example:
        from orka.integrations.openai import OrkaOpenAIAdapter
        from openai import OpenAI
        import orka

        orka.init(api_key="orka_...")
        adapter = OrkaOpenAIAdapter(
            openai_client=OpenAI(),
            agent_id="my-agent",
        )
        response = adapter.run("Summarize the latest agent executions")
        print(response)
    """

    def __init__(
        self,
        openai_client: Any,
        agent_id: str,
        client: "OrkaClient | None" = None,
        model: str = "gpt-4o",
        system_prompt: str = "You are a helpful assistant with access to Orka AI agent management tools.",
        max_tool_rounds: int = 10,
    ):
        self._openai = openai_client
        self._agent_id = agent_id
        self._model = model
        self._system = system_prompt
        self._max_rounds = max_tool_rounds
        if client is None:
            from orka import _client
            self._orka = _client
        else:
            self._orka = client

    def run(self, user_message: str, extra_tools: list[dict] | None = None) -> str:
        tools = orka_tools_schema() + (extra_tools or [])
        messages = [
            {"role": "system", "content": self._system},
            {"role": "user", "content": user_message},
        ]

        for _ in range(self._max_rounds):
            response = self._openai.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
            msg = response.choices[0].message
            messages.append(msg)

            if not msg.tool_calls:
                return msg.content or ""

            for tc in msg.tool_calls:
                result = handle_orka_tool_call(tc, self._orka)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

        return "[Orka] Max tool rounds reached."
