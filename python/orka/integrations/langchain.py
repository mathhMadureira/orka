"""LangChain integration for Orka.

Install:
    pip install "orkaia[langchain]"

Usage:
    import orka
    from orka.integrations.langchain import OrkaCallbackHandler
    from langchain_openai import ChatOpenAI

    orka.init(api_key="orka_...")

    # Every LLM call, tool use, and chain step is logged to Orka
    cb  = OrkaCallbackHandler(agent_id="my-agent")
    llm = ChatOpenAI(model="gpt-4o", callbacks=[cb])
    result = llm.invoke("Summarize this document...")

    # Or use the decorator for full guard + audit:
    @orka.guard(agent_id="my-agent", task_type="langchain_run")
    def run_chain(text: str) -> str:
        return llm.invoke(text).content
"""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    pass

try:
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.outputs import LLMResult
except ImportError as e:
    raise ImportError(
        "langchain-core is required. Install with: pip install 'orkaia[langchain]'"
    ) from e


class OrkaCallbackHandler(BaseCallbackHandler):
    """LangChain callback handler that sends audit events to Orka's X-Ledger.

    Attach to any LLM, chain, or AgentExecutor to get a full audit trail
    of every LLM call, tool invocation, and chain step inside your Orka dashboard.

    Example:
        from orka.integrations.langchain import OrkaCallbackHandler

        cb = OrkaCallbackHandler(agent_id="my-langchain-agent")
        llm = ChatOpenAI(model="gpt-4o", callbacks=[cb])
    """

    def __init__(self, agent_id: str, client: Any = None):
        super().__init__()
        self._agent_id = agent_id
        if client is None:
            from orka import _client
            self._client = _client
        else:
            self._client = client

    def _emit(self, task_type: str, payload: dict, status: str = "COMPLETED") -> None:
        if self._client is None:
            return
        try:
            self._client.log_execution(
                agent_id=self._agent_id,
                task_type=task_type,
                status=status,
                input_payload=payload,
                output_payload=None,
                duration_ms=0,
            )
        except Exception:
            pass  # audit is best-effort — never block the chain

    def on_llm_start(self, serialized: dict, prompts: list[str], **kwargs: Any) -> None:
        self._emit("langchain.llm_start", {
            "model": serialized.get("name") or serialized.get("id", [""])[- 1],
            "prompt_count": len(prompts),
        })

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        self._emit("langchain.llm_end", {
            "generations": len(response.generations),
            "token_usage": response.llm_output.get("token_usage", {}) if response.llm_output else {},
        })

    def on_tool_start(self, serialized: dict, input_str: str, **kwargs: Any) -> None:
        self._emit("langchain.tool_start", {
            "tool": serialized.get("name"),
            "input": input_str[:500],
        })

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        self._emit("langchain.tool_end", {"output": str(output)[:500]})

    def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        self._emit("langchain.tool_error", {"error": str(error)}, status="FAILED")

    def on_chain_start(self, serialized: dict, inputs: dict, **kwargs: Any) -> None:
        self._emit("langchain.chain_start", {"chain": serialized.get("name")})

    def on_chain_end(self, outputs: dict, **kwargs: Any) -> None:
        self._emit("langchain.chain_end", {})

    def on_agent_action(self, action: Any, **kwargs: Any) -> None:
        self._emit("langchain.agent_action", {
            "tool": action.tool,
            "input": str(action.tool_input)[:500],
        })

    def on_agent_finish(self, finish: Any, **kwargs: Any) -> None:
        self._emit("langchain.agent_finish", {
            "output": str(finish.return_values)[:500],
        })
