from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np

from ..core.models import Bar


@dataclass(frozen=True)
class Series:
    """OHLCV em arrays numpy (formato que a matemática consome)."""

    symbol: str
    ts: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray

    def __len__(self) -> int:
        return len(self.close)

    @classmethod
    def from_bars(cls, symbol: str, bars: list[Bar]) -> "Series":
        return cls(
            symbol,
            np.array([b.ts for b in bars], dtype=object),
            *(np.array([getattr(b, f) for b in bars], dtype=float)
              for f in ("open", "high", "low", "close", "volume")),
        )

    def upto(self, i: int) -> "Series":
        """Visão causal: barras [0, i] inclusive. Usada pelo backtest para impedir look-ahead."""
        s = slice(0, i + 1)
        return Series(self.symbol, self.ts[s], self.open[s], self.high[s], self.low[s],
                      self.close[s], self.volume[s])

    def tail(self, n: int) -> "Series":
        s = slice(max(0, len(self) - n), len(self))
        return Series(self.symbol, self.ts[s], self.open[s], self.high[s], self.low[s],
                      self.close[s], self.volume[s])

    @property
    def last_ts(self) -> datetime:
        return self.ts[-1]
