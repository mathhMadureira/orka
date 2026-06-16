from __future__ import annotations

from typing import Any

import httpx

from .exceptions import OrkaAuthError, OrkaConnectionError, OrkaPolicyBlocked

DEFAULT_BASE_URL = "https://orka-backend.onrender.com/api/v1"


class OrkaClient:
    """Synchronous Orka client.

    Two usage patterns:

    1. Decorator-based (simplest):
        import orka
        orka.init(api_key="orka_...")

        @orka.guard(agent_id="my-agent", task_type="summarize")
        def run(text): ...

    2. Resource-based (full control):
        from orka import OrkaClient
        client = OrkaClient(api_key="orka_...")
        agent = client.agents.create(name="my-agent", endpoint_url="https://...")
        execution = client.executions.create(agent_id=agent["id"], task_type="summarize", payload={"text": "..."})
    """

    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL, timeout: float = 30.0):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        }
        self._timeout = timeout
        self.agents = _AgentsResource(self)
        self.executions = _ExecutionsResource(self)
        self.handover = _HandoverResource(self)

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                r = client.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=self._headers,
                    **kwargs,
                )
            if r.status_code == 401:
                raise OrkaAuthError("Invalid API key")
            if r.status_code == 403:
                data = r.json() if r.content else {}
                raise OrkaPolicyBlocked(
                    reason=data.get("reason", "Policy denied"),
                    policy_name=data.get("policy_name"),
                )
            r.raise_for_status()
            return r.json() if r.content else {}
        except httpx.ConnectError as e:
            raise OrkaConnectionError(f"Cannot reach Orka at {self.base_url}") from e

    async def _request_async(self, method: str, path: str, **kwargs) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                r = await client.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=self._headers,
                    **kwargs,
                )
            if r.status_code == 401:
                raise OrkaAuthError("Invalid API key")
            if r.status_code == 403:
                data = r.json() if r.content else {}
                raise OrkaPolicyBlocked(
                    reason=data.get("reason", "Policy denied"),
                    policy_name=data.get("policy_name"),
                )
            r.raise_for_status()
            return r.json() if r.content else {}
        except httpx.ConnectError as e:
            raise OrkaConnectionError(f"Cannot reach Orka at {self.base_url}") from e

    # ── Internal methods used by @guard decorator ────────────────────────────

    def check_policy(self, agent_id: str, task_type: str, payload: dict) -> dict:
        return self._request("POST", "/xshield/check", json={
            "agent_id": agent_id,
            "task_type": task_type,
            "payload": payload,
        })

    async def check_policy_async(self, agent_id: str, task_type: str, payload: dict) -> dict:
        return await self._request_async("POST", "/xshield/check", json={
            "agent_id": agent_id,
            "task_type": task_type,
            "payload": payload,
        })

    def log_execution(
        self,
        agent_id: str,
        task_type: str,
        status: str,
        input_payload: dict,
        output_payload: Any = None,
        error: str | None = None,
        duration_ms: int = 0,
    ) -> dict:
        return self._request("POST", "/executions", json={
            "requesting_agent_id": agent_id,
            "executing_agent_target": agent_id,
            "task_type": task_type,
            "task_payload": input_payload,
            "status": status,
            "output_payload": output_payload,
            "error": error,
            "duration_ms": duration_ms,
        })

    async def log_execution_async(
        self,
        agent_id: str,
        task_type: str,
        status: str,
        input_payload: dict,
        output_payload: Any = None,
        error: str | None = None,
        duration_ms: int = 0,
    ) -> dict:
        return await self._request_async("POST", "/executions", json={
            "requesting_agent_id": agent_id,
            "executing_agent_target": agent_id,
            "task_type": task_type,
            "task_payload": input_payload,
            "status": status,
            "output_payload": output_payload,
            "error": error,
            "duration_ms": duration_ms,
        })


class _AgentsResource:
    def __init__(self, client: OrkaClient):
        self._c = client

    def list(self) -> list[dict]:
        return self._c._request("GET", "/agents")

    def get(self, agent_id: str) -> dict:
        return self._c._request("GET", f"/agents/{agent_id}")

    def create(
        self,
        *,
        name: str,
        endpoint_url: str,
        protocol: str = "REST",
        domain: str = "general",
        capabilities: list[str] | None = None,
        description: str | None = None,
        trust_level: str = "LOW",
        max_daily_executions: int = 0,
    ) -> dict:
        return self._c._request("POST", "/agents", json={
            "name": name,
            "endpoint_url": endpoint_url,
            "protocol": protocol,
            "domain": domain,
            "capabilities": capabilities or [],
            "description": description,
            "trust_level": trust_level,
            "max_daily_executions": max_daily_executions,
        })

    def update(self, agent_id: str, **fields) -> dict:
        return self._c._request("PATCH", f"/agents/{agent_id}", json=fields)

    def delete(self, agent_id: str) -> None:
        self._c._request("DELETE", f"/agents/{agent_id}")

    def stats(self, agent_id: str) -> dict:
        return self._c._request("GET", f"/agents/{agent_id}/stats")


class _ExecutionsResource:
    def __init__(self, client: OrkaClient):
        self._c = client

    def list(self, agent_id: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
        params: dict = {"limit": limit, "offset": offset}
        if agent_id:
            params["agent_id"] = agent_id
        return self._c._request("GET", "/executions", params=params)

    def get(self, execution_id: str) -> dict:
        return self._c._request("GET", f"/executions/{execution_id}")

    def create(
        self,
        *,
        agent_id: str,
        task_type: str,
        payload: dict | None = None,
        callback_url: str | None = None,
    ) -> dict:
        body: dict = {
            "requesting_agent_id": agent_id,
            "executing_agent_target": agent_id,
            "task_type": task_type,
            "task_payload": payload or {},
        }
        if callback_url:
            body["callback_url"] = callback_url
        return self._c._request("POST", "/executions", json=body)

    def events(self, execution_id: str) -> list[dict]:
        return self._c._request("GET", f"/executions/{execution_id}/events")


class _HandoverResource:
    def __init__(self, client: OrkaClient):
        self._c = client

    def request(
        self,
        *,
        from_agent_id: str,
        to_agent_id: str,
        task_type: str,
        payload: dict,
        callback_url: str | None = None,
    ) -> dict:
        body: dict = {
            "requesting_agent_id": from_agent_id,
            "executing_agent_target": to_agent_id,
            "task_type": task_type,
            "task_payload": payload,
        }
        if callback_url:
            body["callback_url"] = callback_url
        return self._c._request("POST", "/handover/request", json=body)

    def get(self, task_id: str) -> dict:
        return self._c._request("GET", f"/handover/{task_id}")
