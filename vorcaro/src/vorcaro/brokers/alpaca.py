"""Ações dos EUA via Alpaca (REST). Em modo não-live usa paper-api.alpaca.markets.

Ordens com stop/alvo são enviadas como *bracket orders* nativas da corretora, então a proteção
existe no servidor mesmo que o Vorcaro caia.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import numpy as np
import requests

from ..core.models import Order, OrderStatus, OrderType, Position
from ..core.money import D
from ..data.series import Series
from .base import Broker, BrokerError

_TF = {"1m": "1Min", "5m": "5Min", "15m": "15Min", "1h": "1Hour", "1d": "1Day"}


class AlpacaBroker(Broker):
    name = "alpaca"

    def __init__(self, *, live: bool = False, session: requests.Session | None = None):
        self.live = live
        self.base = "https://api.alpaca.markets" if live else "https://paper-api.alpaca.markets"
        self.data = "https://data.alpaca.markets"
        key, sec = os.getenv("VORCARO_ALPACA_KEY_ID"), os.getenv("VORCARO_ALPACA_SECRET")
        if not key or not sec:
            raise BrokerError("defina VORCARO_ALPACA_KEY_ID e VORCARO_ALPACA_SECRET")
        self.s = session or requests.Session()
        self.s.headers.update({"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec})

    def _req(self, method: str, url: str, **kw) -> dict | list:
        r = self.s.request(method, url, timeout=15, **kw)
        if r.status_code >= 400:
            raise BrokerError(f"Alpaca {r.status_code}: {r.text[:300]}")
        return r.json() if r.content else {}

    def equity(self) -> Decimal:
        return D(self._req("GET", f"{self.base}/v2/account")["equity"])

    def cash(self) -> Decimal:
        return D(self._req("GET", f"{self.base}/v2/account")["cash"])

    def positions(self) -> dict[str, Position]:
        return {p["symbol"]: Position(p["symbol"], D(p["qty"]), D(p["avg_entry_price"]))
                for p in self._req("GET", f"{self.base}/v2/positions")}

    def submit(self, order: Order) -> Order:
        body: dict = {"symbol": order.symbol, "qty": str(order.qty), "side": order.side.value,
                      "type": order.type.value, "time_in_force": "day",
                      "client_order_id": order.client_id}
        if order.type is OrderType.LIMIT:
            body["limit_price"] = str(order.limit_price)
        if order.stop_loss is not None and order.take_profit is not None:
            body["order_class"] = "bracket"
            body["take_profit"] = {"limit_price": str(order.take_profit)}
            body["stop_loss"] = {"stop_price": str(order.stop_loss)}
        try:
            r = self._req("POST", f"{self.base}/v2/orders", json=body)
        except BrokerError:
            order.status = OrderStatus.REJECTED
            raise
        order.broker_id = r["id"]
        order.status = OrderStatus.FILLED if r.get("status") == "filled" else OrderStatus.NEW
        return order

    def cancel(self, order: Order) -> None:
        if order.broker_id:
            self._req("DELETE", f"{self.base}/v2/orders/{order.broker_id}")
            order.status = OrderStatus.CANCELED

    def bars(self, symbol: str, timeframe: str = "5m", limit: int = 500) -> Series:
        start = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        r = self._req("GET", f"{self.data}/v2/stocks/{symbol}/bars",
                      params={"timeframe": _TF[timeframe], "limit": limit, "start": start,
                              "adjustment": "all", "feed": "iex"})
        b = r.get("bars") or []
        if not b:
            raise BrokerError(f"sem barras para {symbol}")
        ts = np.array([datetime.fromisoformat(x["t"].replace("Z", "+00:00")) for x in b], dtype=object)
        f = lambda k: np.array([x[k] for x in b], dtype=float)  # noqa: E731
        return Series(symbol, ts, f("o"), f("h"), f("l"), f("c"), f("v")).tail(limit)
