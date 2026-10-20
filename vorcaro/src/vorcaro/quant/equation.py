r"""A Equação Vorcaro (Ω).

Combina cinco medidas que respondem perguntas diferentes:

    regime        H  — expoente de Hurst dos log-retornos: o mercado está em tendência ou
                       revertendo à média?
    momentum      M  = (EMA_f − EMA_s) / ATR                    (em unidades de volatilidade)
    reversão      Z  = (C − VWAP_n) / σ_n                       (desvio padronizado do preço justo)
    padrão        B  = 2·p̂ − 1 do padrão binário significativo  (0 se nenhum casar)
    incerteza     ε  = H(X_t | X_{t−L..t−1}) / log|A|           (entropia condicional normalizada)

O regime decide QUANTO confiar em momentum versus reversão através de uma porta logística:

    α = 1 / (1 + e^{−κ (H − ½)})          α→1 em tendência, α→0 em reversão

E a equação:

    Ψ = tanh( α · M/λ_M  −  (1−α) · Z/λ_Z  +  β · B )
    Ω = Ψ · (1 − w_ε · ε) · (1 − e^{−N/N₀})

O fator (1 − w_ε·ε) derruba a convicção quando o fluxo de bits está próximo do aleatório
(ε→1 corta até w_ε da convicção; ε estimada com correção de viés de Miller-Madow);
o fator (1 − e^{−N/N₀}) penaliza históricos curtos. Ω ∈ [−1, 1]: sinal = direção,
módulo = convicção.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..data.series import Series
from . import indicators as ind
from .binary import BinaryEncoder, BinaryPatternMiner, conditional_entropy_rate
from .stats import hurst_rs


@dataclass(frozen=True)
class OmegaParams:
    ema_fast: int = 9
    ema_slow: int = 21
    atr_n: int = 14
    vwap_n: int = 30
    hurst_window: int = 256
    kappa: float = 20.0
    lambda_m: float = 1.5
    lambda_z: float = 2.0
    beta: float = 1.0
    w_entropy: float = 0.5
    entropy_order: int = 3
    entropy_window: int = 256
    n0: float = 100.0


@dataclass(frozen=True)
class OmegaReading:
    omega: float
    psi: float
    alpha: float
    hurst: float
    momentum: float
    zscore: float
    pattern_edge: float
    entropy: float

    def explain(self) -> str:
        regime = "tendência" if self.alpha > 0.6 else "reversão" if self.alpha < 0.4 else "neutro"
        return (f"Ω={self.omega:+.3f} Ψ={self.psi:+.3f} H={self.hurst:.3f}({regime}) "
                f"M={self.momentum:+.2f} Z={self.zscore:+.2f} B={self.pattern_edge:+.3f} "
                f"ε={self.entropy:.3f}")


def omega(series: Series, p: OmegaParams = OmegaParams(),
          miner: BinaryPatternMiner | None = None,
          encoder: BinaryEncoder | None = None) -> OmegaReading | None:
    n = len(series)
    need = max(p.ema_slow, p.atr_n, p.vwap_n) + 2
    if n < need:
        return None
    c, h, l, v = series.close, series.high, series.low, series.volume
    rets = ind.log_returns(c)

    a = ind.atr(h, l, c, p.atr_n)[-1]
    m = (ind.ema(c, p.ema_fast)[-1] - ind.ema(c, p.ema_slow)[-1]) / a if a > 0 else 0.0

    vw = ind.vwap(h, l, c, v, p.vwap_n)[-1]
    sd = np.std(c[-p.vwap_n:], ddof=1)
    z = (c[-1] - vw) / sd if sd > 0 and np.isfinite(vw) else 0.0

    hurst = hurst_rs(rets[-p.hurst_window:])
    alpha = 1.0 / (1.0 + math.exp(-p.kappa * (hurst - 0.5)))

    enc = encoder or BinaryEncoder(ret_bits=1, vol_bit=False)
    sym = enc.encode(rets[-p.entropy_window:], v[1:][-p.entropy_window:] if enc.vol_bit else None)
    eps = conditional_entropy_rate(sym, p.entropy_order, enc.alphabet)

    b = 0.0
    if miner is not None and miner.patterns:
        hit = miner.match(sym)
        if hit is not None:
            b = hit.edge

    psi = math.tanh(alpha * m / p.lambda_m - (1 - alpha) * z / p.lambda_z + p.beta * b)
    om = psi * (1 - p.w_entropy * eps) * (1 - math.exp(-n / p.n0))
    return OmegaReading(float(np.clip(om, -1, 1)), psi, alpha, hurst, float(m), float(z), b, eps)
