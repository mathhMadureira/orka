from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..core.models import Signal
from ..data.series import Series
from ..quant import indicators as ind
from ..quant.binary import BinaryEncoder, BinaryPatternMiner
from ..quant.equation import OmegaParams, omega
from ..quant.stats import hurst_rs
from .base import Agent


class MomentumAgent(Agent):
    """Cruzamento de EMAs normalizado por ATR, confirmado por Hurst > 0.5."""

    name = "momentum"

    def __init__(self, fast: int = 9, slow: int = 21, atr_n: int = 14, hurst_window: int = 256,
                 lookback: int = 400):
        self.fast, self.slow, self.atr_n, self.hw = fast, slow, atr_n, hurst_window
        self.lookback = lookback

    def analyze(self, s: Series) -> Signal | None:
        s = s.tail(self.lookback)
        if len(s) < self.slow + self.atr_n:
            return None
        a = ind.atr(s.high, s.low, s.close, self.atr_n)[-1]
        if not a > 0:
            return None
        m = (ind.ema(s.close, self.fast)[-1] - ind.ema(s.close, self.slow)[-1]) / a
        h = hurst_rs(ind.log_returns(s.close)[-self.hw:])
        conf = max(0.0, min(1.0, (h - 0.45) * 5)) * min(1.0, abs(m) / 2)
        return self._signal(s, math.tanh(m), conf, f"M={m:+.2f} ATR, H={h:.2f}")


class MeanReversionAgent(Agent):
    """Desvio do VWAP em desvios padrão + RSI extremo, confirmado por Hurst < 0.5."""

    name = "mean_reversion"

    def __init__(self, n: int = 30, rsi_n: int = 14, hurst_window: int = 256, lookback: int = 400):
        self.n, self.rsi_n, self.hw = n, rsi_n, hurst_window
        self.lookback = lookback

    def analyze(self, s: Series) -> Signal | None:
        s = s.tail(self.lookback)
        if len(s) < self.n + 2:
            return None
        vw = ind.vwap(s.high, s.low, s.close, s.volume, self.n)[-1]
        sd = np.std(s.close[-self.n:], ddof=1)
        if not (sd > 0 and np.isfinite(vw)):
            return None
        z = (s.close[-1] - vw) / sd
        r = ind.rsi(s.close, self.rsi_n)[-1]
        h = hurst_rs(ind.log_returns(s.close)[-self.hw:])
        extreme = abs(r - 50) / 50 if np.isfinite(r) else 0.0
        conf = max(0.0, min(1.0, (0.55 - h) * 5)) * min(1.0, abs(z) / 2.5) * (0.5 + 0.5 * extreme)
        return self._signal(s, -math.tanh(z / 1.5), conf, f"Z={z:+.2f}, RSI={r:.1f}, H={h:.2f}")


@dataclass
class BinaryPatternAgent(Agent):
    """Opera padrões binários estatisticamente significativos (FDR controlada).

    Re-treina a cada ``refit_every`` barras usando APENAS a janela passada.
    """

    name: str = "binary_pattern"
    train_window: int = 2000
    refit_every: int = 100
    ret_bits: int = 1
    vol_bit: bool = True
    miner_kwargs: dict = field(default_factory=dict)
    _cache: dict[str, tuple[int, BinaryEncoder, BinaryPatternMiner]] = field(default_factory=dict)

    def _model(self, s: Series) -> tuple[BinaryEncoder, BinaryPatternMiner]:
        n = len(s)
        cached = self._cache.get(s.symbol)
        if cached and n - cached[0] < self.refit_every:
            return cached[1], cached[2]
        r = ind.log_returns(s.close)[-self.train_window:]
        v = s.volume[1:][-self.train_window:]
        enc = BinaryEncoder(self.ret_bits, self.vol_bit).fit(r[:-1])
        sym = enc.encode(r, v if self.vol_bit else None)
        # alvo de sym[t] é r[t+1]; a última barra não tem alvo e fica de fora do treino
        miner = BinaryPatternMiner(**self.miner_kwargs).fit(sym[:-1], r[1:])
        self._cache[s.symbol] = (n, enc, miner)
        return enc, miner

    def miner_for(self, s: Series) -> tuple[BinaryEncoder, BinaryPatternMiner]:
        return self._model(s)

    def analyze(self, s: Series) -> Signal | None:
        if len(s) < 300:
            return None
        enc, miner = self._model(s)
        r = ind.log_returns(s.close)[-64:]
        sym = enc.encode(r, s.volume[1:][-64:] if self.vol_bit else None)
        hit = miner.match(sym)
        if hit is None:
            return None
        support = 1 - math.exp(-hit.n / 100)
        conf = min(1.0, abs(hit.edge) * 4) * (1 - hit.q_value) * support
        return self._signal(s, hit.edge * 4, conf,
                            f"padrão {hit.bits(enc.bits_per_symbol)} n={hit.n} "
                            f"p̂={hit.p_post:.3f} q={hit.q_value:.4f}")


class OmegaAgent(Agent):
    """Agente da Equação Vorcaro Ω."""

    name = "omega"

    def __init__(self, params: OmegaParams = OmegaParams(),
                 pattern_agent: BinaryPatternAgent | None = None, lookback: int = 400):
        self.params = params
        self.pattern_agent = pattern_agent
        self.lookback = lookback

    def analyze(self, s: Series) -> Signal | None:
        miner = enc = None
        if self.pattern_agent is not None and len(s) >= 300:
            enc, miner = self.pattern_agent.miner_for(s)
        reading = omega(s.tail(self.lookback), self.params, miner, enc)
        if reading is None:
            return None
        return self._signal(s, reading.omega, min(1.0, abs(reading.omega) * 2), reading.explain())


class SentimentAgent(Agent):
    """Converte sentimento de notícias (raspagem) em sinal. Pontuações em [-1,1] por símbolo."""

    name = "sentiment"

    def __init__(self, scores: dict[str, tuple[float, int]] | None = None):
        self.scores = scores or {}

    def update(self, symbol: str, score: float, n_articles: int) -> None:
        self.scores[symbol] = (score, n_articles)

    def analyze(self, s: Series) -> Signal | None:
        if s.symbol not in self.scores:
            return None
        score, n = self.scores[s.symbol]
        conf = abs(score) * (1 - math.exp(-n / 5))
        return self._signal(s, score, conf, f"sentimento={score:+.2f} em {n} notícias")


class AutocorrelationAgent(Agent):
    r"""Previsão linear de 1 passo a partir da autocorrelação dos retornos.

    ρ̂_k = Σ (r_t − r̄)(r_{t−k} − r̄) / Σ (r_t − r̄)²,   k = 1..K
    Sob H0 (sem memória) ρ̂_k ~ N(0, 1/n) → z_k = ρ̂_k √n. Só lags com |z_k| > z_crit entram:

        r̂_{t+1} = Σ_{k: |z_k|>z_crit} ρ̂_k · r_{t+1−k}

    Direção = tanh(r̂ / σ_r · ganho); confiança = 1 − p-valor do maior |z| (com Bonferroni em K).
    """

    name = "autocorr"

    def __init__(self, window: int = 500, max_lag: int = 3, z_crit: float = 2.5, gain: float = 3.0):
        self.window, self.max_lag, self.z_crit, self.gain = window, max_lag, z_crit, gain

    def analyze(self, s: Series) -> Signal | None:
        r = ind.log_returns(s.close)[-self.window:]
        n = len(r)
        if n < 100:
            return None
        d = r - r.mean()
        den = float((d * d).sum())
        if den == 0:
            return None
        pred, best_z, used = 0.0, 0.0, []
        for k in range(1, self.max_lag + 1):
            rho = float((d[k:] * d[:-k]).sum() / den)
            z = rho * math.sqrt(n)
            if abs(z) > self.z_crit:
                pred += rho * d[-k]
                used.append(f"ρ{k}={rho:+.3f}")
            best_z = max(best_z, abs(z))
        if not used:
            return None
        from ..quant.stats import norm_cdf

        p = min(1.0, 2 * (1 - norm_cdf(best_z)) * self.max_lag)
        sd = float(r.std(ddof=1))
        return self._signal(s, math.tanh(pred / sd * self.gain), 1 - p,
                            f"{' '.join(used)} r̂={pred:+.5f}")
