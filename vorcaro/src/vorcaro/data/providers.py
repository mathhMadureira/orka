"""Fontes de dados de mercado. As públicas não exigem chave."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests

from .series import Series

UA = {"User-Agent": "Mozilla/5.0 (Vorcaro research bot)"}
# o espelho .vision serve dados públicos onde api.binance.com é bloqueado
BINANCE_HOSTS = ("https://api.binance.com", "https://data-api.binance.vision")


def load_csv(path: str | Path, symbol: str | None = None) -> Series:
    """CSV com colunas: timestamp,open,high,low,close,volume (timestamp ISO-8601 ou epoch s/ms)."""
    path = Path(path)
    rows = list(csv.DictReader(path.open()))
    if not rows:
        raise ValueError(f"{path} vazio")
    key = {k.lower(): k for k in rows[0]}
    tcol = key.get("timestamp") or key.get("time") or key.get("date") or key.get("datetime")

    def ts(v: str) -> datetime:
        try:
            x = float(v)
            return datetime.fromtimestamp(x / 1000 if x > 1e11 else x, timezone.utc)
        except ValueError:
            d = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

    f = lambda c: np.array([float(r[key[c]]) for r in rows])  # noqa: E731
    return Series(symbol or path.stem, np.array([ts(r[tcol]) for r in rows], dtype=object),
                  f("open"), f("high"), f("low"), f("close"), f("volume"))


def save_csv(s: Series, path: str | Path) -> None:
    with Path(path).open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for i in range(len(s)):
            w.writerow([s.ts[i].isoformat(), s.open[i], s.high[i], s.low[i], s.close[i], s.volume[i]])


def binance_klines(symbol: str = "BTCUSDT", interval: str = "5m", limit: int = 1000,
                   session: requests.Session | None = None) -> Series:
    """Klines públicos da Binance (sem chave). Pagina para trás se limit > 1000."""
    s = session or requests.Session()
    out: list[list] = []
    end: int | None = None
    while len(out) < limit:
        params = {"symbol": symbol, "interval": interval, "limit": min(1000, limit - len(out))}
        if end is not None:
            params["endTime"] = end
        r = None
        for host in BINANCE_HOSTS:
            try:
                r = s.get(f"{host}/api/v3/klines", params=params, headers=UA, timeout=15)
                r.raise_for_status()
                break
            except requests.RequestException:
                r = None
        if r is None:
            raise OSError(f"nenhum host da Binance acessível: {BINANCE_HOSTS}")
        batch = r.json()
        if not batch:
            break
        out = batch + out
        end = batch[0][0] - 1
    a = np.array([[float(x) for x in row[:6]] for row in out])
    ts = np.array([datetime.fromtimestamp(t / 1000, timezone.utc) for t in a[:, 0]], dtype=object)
    return Series(symbol, ts, a[:, 1], a[:, 2], a[:, 3], a[:, 4], a[:, 5])


def yahoo_chart(symbol: str, interval: str = "5m", range_: str = "30d",
                session: requests.Session | None = None) -> Series:
    """Endpoint público de gráficos do Yahoo. Ações B3 usam sufixo .SA (ex.: PETR4.SA)."""
    s = session or requests.Session()
    r = s.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
              params={"interval": interval, "range": range_}, headers=UA, timeout=15)
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    cols = [np.array(q[k], dtype=float) for k in ("open", "high", "low", "close", "volume")]
    ok = np.all([np.isfinite(c) for c in cols], axis=0)
    ts = np.array([datetime.fromtimestamp(t, timezone.utc) for t in res["timestamp"]], dtype=object)
    return Series(symbol, ts[ok], *(c[ok] for c in cols))


def synthetic(n: int = 3000, seed: int = 7, symbol: str = "SYN", mu: float = 0.0,
              sigma: float = 0.002, start: float = 100.0, regime_switch: int = 0,
              ar: float = 0.0) -> Series:
    """Série sintética: passeio log-normal com AR(1) opcional nos retornos e troca de regime.

    ar>0 cria tendência (persistência), ar<0 cria reversão. regime_switch alterna o sinal
    de ar a cada N barras. Útil para testar se os agentes encontram estrutura onde ela existe
    — e NÃO encontram onde ela não existe (ar=0).
    """
    rng = np.random.default_rng(seed)
    eps = rng.standard_normal(n) * sigma
    r = np.empty(n)
    phi = ar
    prev = 0.0
    for i in range(n):
        if regime_switch and i and i % regime_switch == 0:
            phi = -phi
        prev = mu + phi * prev + eps[i]
        r[i] = prev
    close = start * np.exp(np.cumsum(r))
    open_ = np.concatenate([[start], close[:-1]])
    wick = np.abs(rng.standard_normal(n)) * sigma * close
    high = np.maximum(open_, close) + wick
    low = np.minimum(open_, close) - wick
    vol = rng.lognormal(10, 0.5, n) * (1 + 50 * np.abs(r))
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()
    ts = np.array([datetime.fromtimestamp(t0 + 300 * i, timezone.utc) for i in range(n)], dtype=object)
    return Series(symbol, ts, open_, high, low, close, vol)
