r"""Conselho de agentes com pesos aprendidos online (Hedge / pesos exponenciais).

Cada agente i tem peso w_i. A decisão é a média ponderada das forças s_i = d_i · c_i:

    S = Σ w_i s_i / Σ_{i: votou} w_i

Depois que o retorno realizado r chega, cada agente sofre perda
ℓ_i = (1 − s_i · sign(r)) / 2 ∈ [0, 1] — quem se absteve recebe ℓ = ½ (neutro), para que
todos sejam comparados nas MESMAS rodadas (premissa do Hedge) — e os pesos são atualizados:

    w_i ← w_i · e^{−η ℓ_i}

O Hedge tem garantia de arrependimento O(√(T ln N)) contra o melhor agente em retrospecto,
então o conselho converge para quem realmente acerta em cada ativo. Os pesos são renormalizados
e têm piso para que nenhum agente morra para sempre (mercados mudam de regime).
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

from ..core.models import Signal
from ..data.series import Series
from .base import Agent


@dataclass(frozen=True)
class Decision:
    symbol: str
    score: float                        # [-1, 1]
    agreement: float                    # [0, 1]: fração do peso que concorda com o sinal final
    signals: tuple[Signal, ...]

    @property
    def direction(self) -> int:
        return 0 if self.score == 0 else (1 if self.score > 0 else -1)

    def explain(self) -> str:
        parts = [f"{s.agent}:{s.strength:+.2f}" for s in self.signals]
        return f"{self.symbol} S={self.score:+.3f} acordo={self.agreement:.0%} [{', '.join(parts)}]"


@dataclass
class Council:
    agents: list[Agent]
    eta: float = 0.1
    weight_floor: float = 0.05
    weights: dict[str, dict[str, float]] = field(default_factory=lambda: defaultdict(dict))
    _pending: dict[str, tuple[Signal, ...]] = field(default_factory=dict)

    def weight(self, symbol: str, agent: str) -> float:
        return self.weights[symbol].get(agent, 1.0)

    def decide(self, series: Series) -> Decision:
        sigs = tuple(sig for a in self.agents if (sig := a.analyze(series)) is not None)
        self._pending[series.symbol] = sigs
        tot = sum(self.weight(series.symbol, s.agent) for s in sigs)
        if not sigs or tot == 0:
            return Decision(series.symbol, 0.0, 0.0, sigs)
        score = sum(self.weight(series.symbol, s.agent) * s.strength for s in sigs) / tot
        agree = sum(self.weight(series.symbol, s.agent) for s in sigs
                    if s.strength * score > 0) / tot
        return Decision(series.symbol, max(-1.0, min(1.0, score)), agree, sigs)

    def learn(self, symbol: str, realized_return: float) -> None:
        sigs = self._pending.pop(symbol, ())
        if not sigs or realized_return == 0:
            return
        sgn = 1.0 if realized_return > 0 else -1.0
        w = self.weights[symbol]
        voted = {s.agent: s.strength for s in sigs}
        for a in self.agents:
            loss = (1 - voted.get(a.name, 0.0) * sgn) / 2
            w[a.name] = self.weight(symbol, a.name) * math.exp(-self.eta * loss)
        total = sum(w.values())
        n = len(w)
        for k in w:
            w[k] = max(self.weight_floor, w[k] / total * n)
