import asyncio
import functools
import time
from typing import Callable, Literal

from .exceptions import OrkaPolicyBlocked

RiskLevel = Literal["UNACCEPTABLE", "HIGH", "LIMITED", "MINIMAL", "NONE"]


def guard(
    agent_id: str,
    task_type: str,
    risk: RiskLevel = "MINIMAL",
    block_on_policy: bool = True,
):
    """
    Decorator that wraps any function with Orka governance.

    - Checks X-Shield policies before execution
    - Logs result to X-Ledger after execution
    - Updates trust score automatically

    Usage:
        @orka.guard(agent_id="uuid", task_type="summarize")
        def my_agent(text: str) -> str:
            return llm.call(text)

        @orka.guard(agent_id="uuid", task_type="transfer", risk="HIGH")
        async def transfer_funds(amount: float) -> dict:
            ...
    """
    def decorator(fn: Callable) -> Callable:
        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                from . import _client  # re-read on every call: orka.init() may run after decoration
                if _client is None:
                    return await fn(*args, **kwargs)

                input_payload = {"args": list(args), "kwargs": kwargs}
                start = time.monotonic()

                try:
                    await _client.check_policy_async(agent_id, task_type, input_payload)
                except OrkaPolicyBlocked:
                    if block_on_policy:
                        raise
                except Exception:
                    pass  # never block execution due to Orka connectivity issues

                error = None
                output = None
                status = "COMPLETED"
                try:
                    output = await fn(*args, **kwargs)
                    return output
                except Exception as e:
                    error = str(e)
                    status = "FAILED"
                    raise
                finally:
                    duration_ms = int((time.monotonic() - start) * 1000)
                    try:
                        await _client.log_execution_async(
                            agent_id=agent_id,
                            task_type=task_type,
                            status=status,
                            input_payload=input_payload,
                            output_payload=str(output) if output is not None else None,
                            error=error,
                            duration_ms=duration_ms,
                        )
                    except Exception:
                        pass  # never break production code due to Orka

            return async_wrapper
        else:
            @functools.wraps(fn)
            def sync_wrapper(*args, **kwargs):
                from . import _client  # re-read on every call: orka.init() may run after decoration
                if _client is None:
                    return fn(*args, **kwargs)

                input_payload = {"args": list(args), "kwargs": kwargs}
                start = time.monotonic()

                try:
                    _client.check_policy(agent_id, task_type, input_payload)
                except OrkaPolicyBlocked:
                    if block_on_policy:
                        raise
                except Exception:
                    pass

                error = None
                output = None
                status = "COMPLETED"
                try:
                    output = fn(*args, **kwargs)
                    return output
                except Exception as e:
                    error = str(e)
                    status = "FAILED"
                    raise
                finally:
                    duration_ms = int((time.monotonic() - start) * 1000)
                    try:
                        _client.log_execution(
                            agent_id=agent_id,
                            task_type=task_type,
                            status=status,
                            input_payload=input_payload,
                            output_payload=str(output) if output is not None else None,
                            error=error,
                            duration_ms=duration_ms,
                        )
                    except Exception:
                        pass

            return sync_wrapper

    return decorator
