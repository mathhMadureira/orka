from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from ..core.models import Order, Position
from ..data.series import Series


class BrokerError(RuntimeError):
    pass


@dataclass(frozen=True)
class Instrument:
    symbol: str
    lot_step: Decimal = Decimal("0.00000001")
    tick: Decimal = Decimal("0.01")
    min_notional: Decimal = Decimal(0)


class Broker(ABC):
    """Interface única para qualquer corretora/carteira."""

    name: str = "broker"
    live: bool = False

    @abstractmethod
    def equity(self) -> Decimal: ...

    @abstractmethod
    def cash(self) -> Decimal: ...

    @abstractmethod
    def positions(self) -> dict[str, Position]: ...

    @abstractmethod
    def submit(self, order: Order) -> Order: ...

    @abstractmethod
    def cancel(self, order: Order) -> None: ...

    @abstractmethod
    def bars(self, symbol: str, timeframe: str = "5m", limit: int = 500) -> Series: ...

    def instrument(self, symbol: str) -> Instrument:
        return Instrument(symbol)

    def close_position(self, symbol: str) -> Order | None:
        from ..core.models import Side

        pos = self.positions().get(symbol)
        if pos is None or pos.qty == 0:
            return None
        side = Side.SELL if pos.qty > 0 else Side.BUY
        return self.submit(Order(symbol, side, abs(pos.qty)))
