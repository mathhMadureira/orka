"""Corretora simulada com contabilidade exata em Decimal.

- Ordens a mercado executam no preço de referência ± slippage (bps) e pagam taxa (bps).
- Stops/alvos são verificados barra a barra; se ambos forem tocados na mesma barra, assume-se
  o PIOR caso (stop primeiro) — premissa conservadora que evita backtests otimistas.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from ..core.models import Bar, Fill, Order, OrderStatus, OrderType, Position, Side
from ..core.money import D
from ..data.series import Series
from .base import Broker, BrokerError, Instrument


class PaperBroker(Broker):
    name = "paper"

    def __init__(self, cash: Decimal | str | float = "100000", fee_bps: float = 5.0,
                 slippage_bps: float = 2.0, data: dict[str, Series] | None = None):
        self._cash = D(cash)
        self.fee = D(fee_bps) / D(10_000)
        self.slip = D(slippage_bps) / D(10_000)
        self._pos: dict[str, Position] = {}
        self._marks: dict[str, Decimal] = {}
        self.fills: list[Fill] = []
        self.orders: list[Order] = []
        self._data = data or {}
        self._now: datetime = datetime.now(timezone.utc)

    # ---- estado ----
    def cash(self) -> Decimal:
        return self._cash

    def equity(self) -> Decimal:
        return self._cash + sum((p.qty * self._marks.get(s, p.avg_price) for s, p in self._pos.items()),
                                Decimal(0))

    def positions(self) -> dict[str, Position]:
        return {s: p for s, p in self._pos.items() if p.qty != 0}

    def mark(self, symbol: str, price: float | Decimal, ts: datetime | None = None) -> None:
        self._marks[symbol] = D(price)
        if ts is not None:
            self._now = ts

    def bars(self, symbol: str, timeframe: str = "5m", limit: int = 500) -> Series:
        if symbol not in self._data:
            raise BrokerError(f"sem dados para {symbol} no PaperBroker")
        return self._data[symbol].tail(limit)

    # ---- execução ----
    def submit(self, order: Order) -> Order:
        ref = self._marks.get(order.symbol)
        if ref is None:
            order.status = OrderStatus.REJECTED
            raise BrokerError(f"sem preço de referência para {order.symbol}")
        if order.type is OrderType.LIMIT:
            if order.limit_price is None:
                raise BrokerError("ordem limitada sem preço")
            marketable = (order.side is Side.BUY and ref <= order.limit_price) or \
                         (order.side is Side.SELL and ref >= order.limit_price)
            if not marketable:
                order.status = OrderStatus.CANCELED  # IOC no simulador
                self.orders.append(order)
                return order
        px = ref * (1 + self.slip * order.side.sign)
        self._fill(order, px)
        return order

    def _fill(self, order: Order, px: Decimal) -> None:
        notional = px * order.qty
        fee = notional * self.fee
        self._cash -= notional * order.side.sign + fee
        pos = self._pos.setdefault(order.symbol, Position(order.symbol))
        was_flat = pos.qty == 0
        pos.apply(Fill(order.client_id, order.symbol, order.side, order.qty, px, fee, self._now))
        if order.stop_loss is not None or order.take_profit is not None:
            if was_flat or pos.stop_loss is None:
                pos.stop_loss, pos.take_profit = order.stop_loss, order.take_profit
        order.status = OrderStatus.FILLED
        order.broker_id = order.client_id
        self.fills.append(Fill(order.client_id, order.symbol, order.side, order.qty, px, fee, self._now))
        self.orders.append(order)

    def cancel(self, order: Order) -> None:
        order.status = OrderStatus.CANCELED

    def check_brackets(self, symbol: str, bar: Bar) -> Fill | None:
        """Dispara stop/alvo se tocados na barra. Stop tem prioridade (pior caso)."""
        pos = self._pos.get(symbol)
        if pos is None or pos.qty == 0:
            return None
        long = pos.qty > 0
        lo, hi, op = D(bar.low), D(bar.high), D(bar.open)
        exit_px: Decimal | None = None
        if pos.stop_loss is not None and ((long and lo <= pos.stop_loss) or (not long and hi >= pos.stop_loss)):
            # gap além do stop executa na abertura (pior que o stop)
            exit_px = min(op, pos.stop_loss) if long else max(op, pos.stop_loss)
        elif pos.take_profit is not None and ((long and hi >= pos.take_profit) or (not long and lo <= pos.take_profit)):
            exit_px = pos.take_profit
        if exit_px is None:
            return None
        side = Side.SELL if long else Side.BUY
        o = Order(symbol, side, abs(pos.qty))
        self._now = bar.ts
        self._fill(o, exit_px * (1 + self.slip * side.sign))
        return self.fills[-1]

    def instrument(self, symbol: str) -> Instrument:
        return Instrument(symbol)
