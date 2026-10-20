"""Cripto via CCXT (Binance, Bybit, OKX, Kraken, Mercado Bitcoin, ...).

Em modo não-live usa o *sandbox/testnet* da exchange. Stops são gerenciados pelo motor do
Vorcaro (lado cliente) para funcionar de forma uniforme entre exchanges spot.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal

import numpy as np

from ..core.models import Order, OrderStatus, OrderType, Position
from ..core.money import D
from ..data.series import Series
from .base import Broker, BrokerError, Instrument


class CCXTBroker(Broker):
    name = "ccxt"

    def __init__(self, exchange: str | None = None, *, live: bool = False, quote: str = "USDT"):
        try:
            import ccxt  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise BrokerError("instale com: pip install 'vorcaro[crypto]'") from e
        exchange = exchange or os.getenv("VORCARO_CCXT_EXCHANGE", "binance")
        cls = getattr(ccxt, exchange)
        self.ex = cls({
            "apiKey": os.getenv("VORCARO_CCXT_API_KEY", ""),
            "secret": os.getenv("VORCARO_CCXT_SECRET", ""),
            "enableRateLimit": True,
        })
        self.live = live
        if not live:
            self.ex.set_sandbox_mode(True)
        self.quote = quote
        self.ex.load_markets()
        self._entry: dict[str, Decimal] = {}

    def _balance(self) -> dict:
        return self.ex.fetch_balance()

    def cash(self) -> Decimal:
        return D(self._balance().get("free", {}).get(self.quote, 0) or 0)

    def equity(self) -> Decimal:
        bal = self._balance()
        total = D(bal.get("total", {}).get(self.quote, 0) or 0)
        for asset, amt in bal.get("total", {}).items():
            if asset == self.quote or not amt:
                continue
            sym = f"{asset}/{self.quote}"
            if sym in self.ex.markets:
                total += D(amt) * D(self.ex.fetch_ticker(sym)["last"])
        return total

    def positions(self) -> dict[str, Position]:
        out: dict[str, Position] = {}
        for asset, amt in self._balance().get("total", {}).items():
            sym = f"{asset}/{self.quote}"
            if asset != self.quote and amt and sym in self.ex.markets:
                out[sym] = Position(sym, D(amt), self._entry.get(sym, Decimal(0)))
        return out

    def instrument(self, symbol: str) -> Instrument:
        m = self.ex.market(symbol)
        prec = m.get("precision", {})
        lims = m.get("limits", {})

        def step(v: object, default: str) -> Decimal:
            if v is None:
                return Decimal(default)
            v = D(v)
            # alguns exchanges informam casas decimais (int), outros o passo (tick size)
            return Decimal(1).scaleb(-int(v)) if v >= 1 and v == v.to_integral() else v

        return Instrument(symbol, step(prec.get("amount"), "0.00000001"),
                          step(prec.get("price"), "0.01"),
                          D((lims.get("cost") or {}).get("min") or 0))

    def submit(self, order: Order) -> Order:
        params = {"clientOrderId": order.client_id}
        price = float(order.limit_price) if order.type is OrderType.LIMIT and order.limit_price else None
        try:
            r = self.ex.create_order(order.symbol, order.type.value, order.side.value,
                                     float(order.qty), price, params)
        except Exception as e:
            order.status = OrderStatus.REJECTED
            raise BrokerError(str(e)) from e
        order.broker_id = r.get("id")
        order.status = OrderStatus.FILLED if r.get("status") == "closed" else OrderStatus.NEW
        if r.get("average"):
            self._entry[order.symbol] = D(r["average"])
        return order

    def cancel(self, order: Order) -> None:
        if order.broker_id:
            self.ex.cancel_order(order.broker_id, order.symbol)
            order.status = OrderStatus.CANCELED

    def bars(self, symbol: str, timeframe: str = "5m", limit: int = 500) -> Series:
        rows = self.ex.fetch_ohlcv(symbol, timeframe, limit=limit)
        a = np.array(rows, dtype=float)
        ts = np.array([datetime.fromtimestamp(t / 1000, timezone.utc) for t in a[:, 0]], dtype=object)
        return Series(symbol, ts, a[:, 1], a[:, 2], a[:, 3], a[:, 4], a[:, 5])
