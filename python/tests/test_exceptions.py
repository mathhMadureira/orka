from orka.exceptions import OrkaAuthError, OrkaConnectionError, OrkaError, OrkaPolicyBlocked


def test_orka_policy_blocked_carries_reason_and_policy_name():
    exc = OrkaPolicyBlocked(reason="budget exceeded", policy_name="max-spend")
    assert exc.reason == "budget exceeded"
    assert exc.policy_name == "max-spend"
    assert "budget exceeded" in str(exc)


def test_orka_policy_blocked_policy_name_optional():
    exc = OrkaPolicyBlocked(reason="blocked")
    assert exc.policy_name is None


def test_exception_hierarchy():
    assert issubclass(OrkaPolicyBlocked, OrkaError)
    assert issubclass(OrkaAuthError, OrkaError)
    assert issubclass(OrkaConnectionError, OrkaError)
