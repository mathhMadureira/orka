from __future__ import annotations

import enum
import itertools
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

_order_ids = itertools.count(1)


class Side(enum.Enum):
    BUY = "buy"
    SELL = "sell"

    @property
    def sign(self) -> int:
        return 1 if self is Side.BUY else -1


class OrderType(enum.Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(enum.Enum):
    NEW = "new"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELED = "canceled"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class Bar:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(slots=True)
class Order:
    symbol: str
    side: Side
    qty: Decimal
    type: OrderType = OrderType.MARKET
    limit_price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    client_id: str = field(default_factory=lambda: f"vorcaro-{next(_order_ids)}")
    status: OrderStatus = OrderStatus.NEW
    broker_id: str | None = None
    created: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class Fill:
    order_id: str
    symbol: str
    side: Side
    qty: Decimal
    price: Decimal
    fee: Decimal
    ts: datetime


@dataclass(slots=True)
class Position:
    symbol: str
    qty: Decimal = Decimal(0)          # >0 comprado, <0 vendido
    avg_price: Decimal = Decimal(0)
    realized_pnl: Decimal = Decimal(0)
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None

    def apply(self, fill: Fill) -> Decimal:
        """Aplica um fill pelo método de custo médio. Retorna o PnL realizado deste fill."""
        signed = fill.qty * fill.side.sign
        realized = Decimal(0)
        if self.qty == 0 or (self.qty > 0) == (signed > 0):
            new_qty = self.qty + signed
            self.avg_price = (self.avg_price * abs(self.qty) + fill.price * fill.qty) / abs(new_qty)
            self.qty = new_qty
        else:
            closing = min(abs(signed), abs(self.qty))
            direction = 1 if self.qty > 0 else -1
            realized = (fill.price - self.avg_price) * closing * direction
            self.qty += signed
            if self.qty == 0:
                self.avg_price = Decimal(0)
                self.stop_loss = self.take_profit = None
            elif (self.qty > 0) != (direction > 0):  # virou de lado
                self.avg_price = fill.price
                self.stop_loss = self.take_profit = None
        self.realized_pnl += realized
        return realized

    def unrealized(self, mark: Decimal) -> Decimal:
        return (mark - self.avg_price) * self.qty


@dataclass(frozen=True, slots=True)
class Signal:
    """Opinião de um agente: direção em [-1, 1] e confiança em [0, 1]."""

    agent: str
    symbol: str
    direction: float
    confidence: float
    rationale: str = ""

    def __post_init__(self) -> None:
        if not -1.0 <= self.direction <= 1.0:
            raise ValueError(f"direction fora de [-1,1]: {self.direction}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence fora de [0,1]: {self.confidence}")

    @property
    def strength(self) -> float:
        return self.direction * self.confidence
