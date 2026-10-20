from __future__ import annotations

from abc import ABC, abstractmethod

from ..core.models import Signal
from ..data.series import Series


class Agent(ABC):
    """Um agente observa uma série (apenas o passado) e emite um Signal, ou None se abstém."""

    name: str = "agent"

    @abstractmethod
    def analyze(self, series: Series) -> Signal | None: ...

    def _signal(self, series: Series, direction: float, confidence: float, why: str) -> Signal:
        clip = lambda x, lo, hi: max(lo, min(hi, float(x)))  # noqa: E731
        return Signal(self.name, series.symbol, clip(direction, -1, 1), clip(confidence, 0, 1), why)
