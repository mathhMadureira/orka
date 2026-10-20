"""Estatística implementada do zero (sem scipy) com cuidado numérico."""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

SQRT2 = math.sqrt(2.0)


def norm_cdf(x: float) -> float:
    return 0.5 * math.erfc(-x / SQRT2)


def norm_ppf(p: float) -> float:
    """Inversa da normal (Acklam, erro relativo < 1.15e-9) + 1 passo de Newton (Halley)."""
    if not 0.0 < p < 1.0:
        raise ValueError("p deve estar em (0,1)")
    a = [-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00]
    b = [-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00]
    lo, hi = 0.02425, 1 - 0.02425
    if p < lo:
        q = math.sqrt(-2 * math.log(p))
        x = (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    elif p <= hi:
        q = p - 0.5
        r = q * q
        x = (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    else:
        q = math.sqrt(-2 * math.log(1 - p))
        x = -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    e = norm_cdf(x) - p
    u = e * math.sqrt(2 * math.pi) * math.exp(x * x / 2)
    return x - u / (1 + x * u / 2)


def log_binom_pmf(k: int, n: int, p: float) -> float:
    if p <= 0.0:
        return 0.0 if k == 0 else -math.inf
    if p >= 1.0:
        return 0.0 if k == n else -math.inf
    return (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
            + k * math.log(p) + (n - k) * math.log1p(-p))


def binom_test_two_sided(k: int, n: int, p: float = 0.5) -> float:
    """p-valor exato bilateral (método de mínima verossimilhança, como R/scipy)."""
    if n == 0:
        return 1.0
    lk = log_binom_pmf(k, n, p)
    tol = 1e-7
    total = 0.0
    for i in range(n + 1):
        li = log_binom_pmf(i, n, p)
        if li <= lk + tol:
            total += math.exp(li)
    return min(1.0, total)


def beta_posterior(successes: int, trials: int, a0: float = 1.0, b0: float = 1.0) -> tuple[float, float]:
    """Média e desvio padrão da posterior Beta(a0+k, b0+n-k)."""
    a = a0 + successes
    b = b0 + trials - successes
    mean = a / (a + b)
    var = a * b / ((a + b) ** 2 * (a + b + 1))
    return mean, math.sqrt(var)


def shannon_entropy(symbols: np.ndarray, base: int = 2) -> float:
    _, counts = np.unique(np.asarray(symbols), return_counts=True)
    p = counts / counts.sum()
    return float(-(p * np.log(p)).sum() / math.log(base))


def hurst_rs(x: np.ndarray, min_chunk: int = 8) -> float:
    """Expoente de Hurst por análise R/S (Rescaled Range) sobre retornos.

    H≈0.5 passeio aleatório; H>0.5 persistente (tendência); H<0.5 anti-persistente (reversão).
    Aplica a correção de Anis-Lloyd-Peters para o viés de pequenas amostras.
    """
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < min_chunk * 4:
        return 0.5
    sizes = np.unique(np.floor(np.logspace(math.log10(min_chunk), math.log10(n // 2), 10)).astype(int))
    log_n, log_rs, log_ers = [], [], []
    for s in sizes:
        k = n // s
        chunks = x[: k * s].reshape(k, s)
        dev = chunks - chunks.mean(axis=1, keepdims=True)
        z = np.cumsum(dev, axis=1)
        r = z.max(axis=1) - z.min(axis=1)
        sd = chunks.std(axis=1, ddof=0)
        ok = sd > 0
        if not ok.any():
            continue
        log_n.append(math.log(s))
        log_rs.append(math.log((r[ok] / sd[ok]).mean()))
        log_ers.append(math.log(_expected_rs(int(s))))
    if len(log_n) < 3:
        return 0.5
    slope_obs = np.polyfit(log_n, log_rs, 1)[0]
    slope_exp = np.polyfit(log_n, log_ers, 1)[0]
    return float(np.clip(0.5 + slope_obs - slope_exp, 0.0, 1.0))


@lru_cache(maxsize=4096)
def _expected_rs(n: int) -> float:
    """E[R/S] para ruído branco (Anis-Lloyd com correção de Peters)."""
    front = (n - 0.5) / n
    if n <= 340:
        g = math.gamma((n - 1) / 2) / (math.sqrt(math.pi) * math.gamma(n / 2))
    else:
        g = 1 / math.sqrt(n * math.pi / 2)
    s = sum(math.sqrt((n - i) / i) for i in range(1, n))
    return front * g * s


def sharpe(returns: np.ndarray, periods_per_year: float) -> float:
    r = np.asarray(returns, dtype=float)
    if len(r) < 2 or r.std(ddof=1) == 0:
        return 0.0
    return float(r.mean() / r.std(ddof=1) * math.sqrt(periods_per_year))


def probabilistic_sharpe(returns: np.ndarray, sr_benchmark: float = 0.0) -> float:
    """PSR de Bailey & López de Prado: P(SR verdadeiro > benchmark) ajustado por assimetria
    e curtose. Usa SR por período (não anualizado)."""
    r = np.asarray(returns, dtype=float)
    n = len(r)
    if n < 3 or r.std(ddof=1) == 0:
        return 0.0
    sr = r.mean() / r.std(ddof=1)
    m = r - r.mean()
    s2 = (m ** 2).mean()
    skew = (m ** 3).mean() / s2 ** 1.5
    kurt = (m ** 4).mean() / s2 ** 2
    denom = math.sqrt(max(1e-12, 1 - skew * sr + (kurt - 1) / 4 * sr ** 2))
    return norm_cdf((sr - sr_benchmark) * math.sqrt(n - 1) / denom)


def kelly_fraction(p_win: float, win_loss_ratio: float) -> float:
    """f* = p - (1-p)/b. Negativo => sem vantagem, retorna 0."""
    if win_loss_ratio <= 0:
        return 0.0
    return max(0.0, p_win - (1 - p_win) / win_loss_ratio)


def kelly_continuous(mu: float, sigma: float) -> float:
    """Kelly para retornos log-normais: f* = mu / sigma²."""
    if sigma <= 0:
        return 0.0
    return mu / sigma ** 2


class Kalman1D:
    """Filtro de Kalman de nível local (random walk + ruído) para suavizar preço sem atraso de MA."""

    def __init__(self, q: float = 1e-5, r: float = 1e-3) -> None:
        self.q, self.r = q, r
        self.x: float | None = None
        self.p = 1.0

    def update(self, z: float) -> float:
        if self.x is None:
            self.x = z
            return z
        self.p += self.q
        k = self.p / (self.p + self.r)
        self.x += k * (z - self.x)
        self.p *= 1 - k
        return self.x

    def filter(self, zs: np.ndarray) -> np.ndarray:
        return np.array([self.update(float(z)) for z in zs])


def max_drawdown(equity: np.ndarray) -> float:
    e = np.asarray(equity, dtype=float)
    if len(e) == 0:
        return 0.0
    peak = np.maximum.accumulate(e)
    return float(((e - peak) / peak).min())
