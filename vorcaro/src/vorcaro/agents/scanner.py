"""Agente scanner: percorre o universo e ranqueia oportunidades.

Pontuação de oportunidade:
    O = |S| · acordo · L · V
    L = tanh(volume_financeiro_médio / liquidez_ref)       (liquidez — evita slippage)
    V = exp(−((σ_ATR% − σ*) / σ*)²)                        (volatilidade perto do ideal σ*)
Day trade precisa de movimento suficiente para pagar custos, mas não volatilidade caótica.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..data.series import Series
from ..quant import indicators as ind
from .council import Council, Decision


@dataclass(frozen=True)
class Opportunity:
    symbol: str
    score: float
    decision: Decision
    atr_pct: float
    liquidity: float


class ScannerAgent:
    name = "scanner"

    def __init__(self, council: Council, liquidity_ref: float = 1e6, target_atr_pct: float = 0.004):
        self.council = council
        self.liquidity_ref = liquidity_ref
        self.target = target_atr_pct

    def evaluate(self, s: Series) -> Opportunity | None:
        if len(s) < 50:
            return None
        a = ind.atr(s.high, s.low, s.close, 14)[-1]
        atr_pct = float(a / s.close[-1])
        dollar_vol = float(np.mean(s.close[-50:] * s.volume[-50:]))
        liq = math.tanh(dollar_vol / self.liquidity_ref)
        vol_fit = math.exp(-(((atr_pct - self.target) / self.target) ** 2))
        d = self.council.decide(s)
        return Opportunity(s.symbol, abs(d.score) * d.agreement * liq * vol_fit, d, atr_pct, liq)

    def scan(self, universe: list[Series], top: int = 5) -> list[Opportunity]:
        ops = [o for s in universe if (o := self.evaluate(s)) is not None and o.score > 0]
        return sorted(ops, key=lambda o: o.score, reverse=True)[:top]
