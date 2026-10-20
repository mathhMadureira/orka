"""Indicadores técnicos vetorizados (numpy). Todos são causais: o valor em t usa só dados <= t.

Posições sem histórico suficiente retornam NaN, nunca um valor inventado.
"""

from __future__ import annotations

import numpy as np

Array = np.ndarray


def sma(x: Array, n: int) -> Array:
    x = np.asarray(x, dtype=float)
    out = np.full_like(x, np.nan)
    if len(x) < n:
        return out
    c = np.cumsum(np.insert(x, 0, 0.0))
    out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def ema(x: Array, n: int) -> Array:
    """EMA com alfa = 2/(n+1), semeada pela SMA dos n primeiros valores."""
    x = np.asarray(x, dtype=float)
    out = np.full_like(x, np.nan)
    if len(x) < n:
        return out
    a = 2.0 / (n + 1)
    out[n - 1] = x[:n].mean()
    for i in range(n, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def wilder(x: Array, n: int) -> Array:
    """Média de Wilder (RMA): alfa = 1/n."""
    x = np.asarray(x, dtype=float)
    out = np.full_like(x, np.nan)
    if len(x) < n:
        return out
    out[n - 1] = x[:n].mean()
    for i in range(n, len(x)):
        out[i] = (out[i - 1] * (n - 1) + x[i]) / n
    return out


def rsi(close: Array, n: int = 14) -> Array:
    close = np.asarray(close, dtype=float)
    out = np.full_like(close, np.nan)
    if len(close) <= n:
        return out
    d = np.diff(close)
    up = wilder(np.clip(d, 0, None), n)
    dn = wilder(np.clip(-d, 0, None), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = up / dn
        r = 100 - 100 / (1 + rs)
    r = np.where((dn == 0) & (up > 0), 100.0, r)
    r = np.where((dn == 0) & (up == 0), 50.0, r)
    out[1:] = r
    return out


def true_range(high: Array, low: Array, close: Array) -> Array:
    high, low, close = (np.asarray(a, dtype=float) for a in (high, low, close))
    prev = np.concatenate([[np.nan], close[:-1]])
    tr = np.nanmax(np.vstack([high - low, np.abs(high - prev), np.abs(low - prev)]), axis=0)
    return tr


def atr(high: Array, low: Array, close: Array, n: int = 14) -> Array:
    return wilder(true_range(high, low, close), n)


def rolling_std(x: Array, n: int) -> Array:
    x = np.asarray(x, dtype=float)
    out = np.full_like(x, np.nan)
    if len(x) < n:
        return out
    w = np.lib.stride_tricks.sliding_window_view(x, n)
    out[n - 1:] = w.std(axis=1, ddof=1)
    return out


def zscore(x: Array, n: int) -> Array:
    with np.errstate(divide="ignore", invalid="ignore"):
        return (np.asarray(x, dtype=float) - sma(x, n)) / rolling_std(x, n)


def bollinger(close: Array, n: int = 20, k: float = 2.0) -> tuple[Array, Array, Array]:
    mid = sma(close, n)
    sd = rolling_std(close, n)
    return mid - k * sd, mid, mid + k * sd


def vwap(high: Array, low: Array, close: Array, volume: Array, n: int) -> Array:
    """VWAP móvel de n barras com preço típico (H+L+C)/3."""
    tp = (np.asarray(high) + np.asarray(low) + np.asarray(close)) / 3.0
    v = np.asarray(volume, dtype=float)
    pv = sma(tp * v, n)
    vv = sma(v, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(vv > 0, pv / vv, np.nan)


def log_returns(close: Array) -> Array:
    close = np.asarray(close, dtype=float)
    return np.diff(np.log(close))
