class OrkaError(Exception):
    pass

class OrkaPolicyBlocked(OrkaError):
    def __init__(self, reason: str, policy_name: str | None = None):
        self.reason = reason
        self.policy_name = policy_name
        super().__init__(f"Blocked by policy: {reason}")

class OrkaAuthError(OrkaError):
    pass

class OrkaConnectionError(OrkaError):
    pass
