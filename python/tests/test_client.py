from unittest.mock import MagicMock, patch

import httpx
import pytest

from orka.client import OrkaClient
from orka.exceptions import OrkaAuthError, OrkaConnectionError, OrkaPolicyBlocked


def _fake_response(status_code=200, json_data=None, content=b"{}"):
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    resp.json.return_value = json_data if json_data is not None else {}
    resp.raise_for_status.return_value = None
    return resp


def _fake_sync_client(response):
    instance = MagicMock()
    instance.request.return_value = response
    instance.__enter__.return_value = instance
    instance.__exit__.return_value = False
    return instance


def test_client_sets_headers_from_api_key():
    client = OrkaClient(api_key="orka_test_key")
    assert client._headers["X-API-Key"] == "orka_test_key"
    assert client.base_url == "https://orka-backend.onrender.com/api/v1"


def test_base_url_trailing_slash_is_stripped():
    client = OrkaClient(api_key="k", base_url="https://example.com/api/")
    assert client.base_url == "https://example.com/api"


def test_request_returns_json_on_success():
    client = OrkaClient(api_key="k")
    response = _fake_response(200, {"id": "exec_123", "status": "PENDING"})
    with patch("orka.client.httpx.Client", return_value=_fake_sync_client(response)):
        result = client._request("GET", "/executions/exec_123")
    assert result == {"id": "exec_123", "status": "PENDING"}


def test_request_raises_auth_error_on_401():
    client = OrkaClient(api_key="bad-key")
    response = _fake_response(401, {}, content=b"")
    with patch("orka.client.httpx.Client", return_value=_fake_sync_client(response)):
        with pytest.raises(OrkaAuthError):
            client._request("GET", "/agents")


def test_request_raises_policy_blocked_on_403_with_reason_and_policy_name():
    client = OrkaClient(api_key="k")
    response = _fake_response(403, {"reason": "budget exceeded", "policy_name": "max-spend"})
    with patch("orka.client.httpx.Client", return_value=_fake_sync_client(response)):
        with pytest.raises(OrkaPolicyBlocked) as exc_info:
            client._request("POST", "/executions")
    assert exc_info.value.reason == "budget exceeded"
    assert exc_info.value.policy_name == "max-spend"


def test_request_raises_connection_error_when_unreachable():
    client = OrkaClient(api_key="k")
    fake = MagicMock()
    fake.__enter__.return_value = fake
    fake.__exit__.return_value = False
    fake.request.side_effect = httpx.ConnectError("boom")
    with patch("orka.client.httpx.Client", return_value=fake):
        with pytest.raises(OrkaConnectionError):
            client._request("GET", "/agents")


def test_agents_create_sends_expected_payload():
    client = OrkaClient(api_key="k")
    response = _fake_response(200, {"id": "agent_1"})
    with patch("orka.client.httpx.Client", return_value=_fake_sync_client(response)) as mock_cls:
        client.agents.create(name="my-agent", endpoint_url="https://my-agent.example.com/run")
    instance = mock_cls.return_value.__enter__.return_value
    _, kwargs = instance.request.call_args
    assert kwargs["json"]["name"] == "my-agent"
    assert kwargs["json"]["endpoint_url"] == "https://my-agent.example.com/run"
    assert kwargs["json"]["trust_level"] == "LOW"


def test_executions_create_defaults_payload_to_empty_dict():
    client = OrkaClient(api_key="k")
    response = _fake_response(200, {"id": "exec_1", "status": "PENDING"})
    with patch("orka.client.httpx.Client", return_value=_fake_sync_client(response)) as mock_cls:
        client.executions.create(agent_id="agent_1", task_type="summarize")
    instance = mock_cls.return_value.__enter__.return_value
    _, kwargs = instance.request.call_args
    assert kwargs["json"]["task_payload"] == {}
    assert "callback_url" not in kwargs["json"]


@pytest.mark.asyncio
async def test_check_policy_async_raises_policy_blocked_on_403():
    client = OrkaClient(api_key="k")
    response = _fake_response(403, {"reason": "too risky"})

    fake_async_client = MagicMock()
    fake_async_client.__aenter__.return_value = fake_async_client
    fake_async_client.__aexit__.return_value = False

    async def fake_request(*args, **kwargs):
        return response

    fake_async_client.request = fake_request

    with patch("orka.client.httpx.AsyncClient", return_value=fake_async_client):
        with pytest.raises(OrkaPolicyBlocked):
            await client.check_policy_async("agent-1", "transfer", {"amount": 500})
