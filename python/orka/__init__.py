from .client import OrkaClient
from .decorators import guard
from .exceptions import OrkaAuthError, OrkaConnectionError, OrkaPolicyBlocked

_client: OrkaClient | None = None


def init(api_key: str, base_url: str = "https://orka-backend.onrender.com/api/v1") -> OrkaClient:
    """Initialize the Orka SDK. Call once at startup.

    Args:
        api_key: Your Orka API key (from dashboard → Settings → API Keys)
        base_url: Orka backend URL (default: production)

    Example:
        import orka
        client = orka.init(api_key="orka_your_key_here")
    """
    global _client
    _client = OrkaClient(api_key=api_key, base_url=base_url)
    return _client


__all__ = [
    "init",
    "guard",
    "OrkaClient",
    "OrkaPolicyBlocked",
    "OrkaAuthError",
    "OrkaConnectionError",
]
__version__ = "0.2.0"
