from __future__ import annotations

import os

from .base import Broker, BrokerError


def live_allowed(cli_flag: bool) -> bool:
    """Trava dupla: dinheiro real só com VORCARO_LIVE=1 E a flag --live."""
    return cli_flag and os.getenv("VORCARO_LIVE") == "1"


def make_broker(name: str, *, live_flag: bool = False, **kw) -> Broker:
    if live_flag and not live_allowed(live_flag):
        raise BrokerError("--live exige também VORCARO_LIVE=1 no ambiente")
    live = live_allowed(live_flag)
    if name == "paper":
        from .paper import PaperBroker
        return PaperBroker(**kw)
    if name == "ccxt":
        from .ccxt_broker import CCXTBroker
        return CCXTBroker(live=live, **kw)
    if name == "alpaca":
        from .alpaca import AlpacaBroker
        return AlpacaBroker(live=live, **kw)
    if name == "mt5":
        from .mt5 import MT5Broker
        return MT5Broker(live=live, **kw)
    raise BrokerError(f"corretora desconhecida: {name} (use paper|ccxt|alpaca|mt5)")
