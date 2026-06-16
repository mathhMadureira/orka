import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

import orka
from orka.decorators import guard
from orka.exceptions import OrkaPolicyBlocked


@pytest.fixture(autouse=True)
def reset_client():
    orka._client = None
    yield
    orka._client = None


def test_guard_passes_through_when_client_not_initialized():
    @guard(agent_id="agent-1", task_type="summarize")
    def run(text):
        return text.upper()

    assert run("hello") == "HELLO"


def test_guard_checks_policy_and_logs_completed_execution():
    mock_client = MagicMock()
    orka._client = mock_client

    @guard(agent_id="agent-1", task_type="summarize")
    def run(text):
        return text.upper()

    assert run("hello") == "HELLO"

    args, _ = mock_client.check_policy.call_args
    assert args[0] == "agent-1"
    assert args[1] == "summarize"

    _, log_kwargs = mock_client.log_execution.call_args
    assert log_kwargs["status"] == "COMPLETED"


def test_guard_reads_client_set_after_decoration_time():
    """orka.init() commonly runs *after* module import decorates the function — must still work."""
    @guard(agent_id="agent-1", task_type="summarize")
    def run(text):
        return text.upper()

    mock_client = MagicMock()
    orka._client = mock_client  # set only now, after decoration

    assert run("hello") == "HELLO"
    mock_client.check_policy.assert_called_once()


def test_guard_blocks_when_policy_denies_and_block_on_policy_true():
    mock_client = MagicMock()
    mock_client.check_policy.side_effect = OrkaPolicyBlocked(reason="too risky")
    orka._client = mock_client

    @guard(agent_id="agent-1", task_type="transfer", block_on_policy=True)
    def transfer():
        return "done"

    with pytest.raises(OrkaPolicyBlocked):
        transfer()


def test_guard_continues_when_policy_denies_and_block_on_policy_false():
    mock_client = MagicMock()
    mock_client.check_policy.side_effect = OrkaPolicyBlocked(reason="too risky")
    orka._client = mock_client

    @guard(agent_id="agent-1", task_type="transfer", block_on_policy=False)
    def transfer():
        return "done"

    assert transfer() == "done"


def test_guard_logs_failed_status_and_reraises_on_exception():
    mock_client = MagicMock()
    orka._client = mock_client

    @guard(agent_id="agent-1", task_type="risky_call")
    def boom():
        raise ValueError("kaboom")

    with pytest.raises(ValueError):
        boom()

    _, log_kwargs = mock_client.log_execution.call_args
    assert log_kwargs["status"] == "FAILED"
    assert log_kwargs["error"] == "kaboom"


def test_guard_never_blocks_execution_on_orka_connectivity_issues():
    mock_client = MagicMock()
    mock_client.check_policy.side_effect = RuntimeError("network down")
    mock_client.log_execution.side_effect = RuntimeError("network down")
    orka._client = mock_client

    @guard(agent_id="agent-1", task_type="summarize")
    def run(text):
        return text.upper()

    assert run("hello") == "HELLO"


@pytest.mark.asyncio
async def test_guard_supports_async_functions():
    mock_client = MagicMock()
    mock_client.check_policy_async = AsyncMock(return_value={})
    mock_client.log_execution_async = AsyncMock(return_value={})
    orka._client = mock_client

    @guard(agent_id="agent-1", task_type="summarize")
    async def run(text):
        await asyncio.sleep(0)
        return text.upper()

    result = await run("hello")
    assert result == "HELLO"
    mock_client.check_policy_async.assert_called_once()
    mock_client.log_execution_async.assert_called_once()


@pytest.mark.asyncio
async def test_guard_async_reraises_policy_blocked():
    mock_client = MagicMock()
    mock_client.check_policy_async = AsyncMock(side_effect=OrkaPolicyBlocked(reason="nope"))
    mock_client.log_execution_async = AsyncMock(return_value={})
    orka._client = mock_client

    @guard(agent_id="agent-1", task_type="transfer", block_on_policy=True)
    async def transfer():
        return "done"

    with pytest.raises(OrkaPolicyBlocked):
        await transfer()
