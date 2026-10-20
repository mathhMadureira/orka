from __future__ import annotations

import tomllib
from dataclasses import fields
from decimal import Decimal
from pathlib import Path

from .backtest.engine import BacktestConfig
from .risk.manager import RiskConfig


def _coerce(cls, data: dict):
    kw = {}
    for f in fields(cls):
        if f.name not in data:
            continue
        v = data[f.name]
        if f.type in ("Decimal", Decimal):
            v = Decimal(str(v))
        elif f.name == "blocked":
            v = frozenset(v)
        kw[f.name] = v
    unknown = set(data) - {f.name for f in fields(cls)}
    if unknown:
        raise ValueError(f"chaves desconhecidas em [{cls.__name__}]: {sorted(unknown)}")
    return cls(**kw)


def load(path: str | Path | None) -> tuple[RiskConfig, BacktestConfig]:
    if path is None:
        return RiskConfig(), BacktestConfig()
    raw = tomllib.loads(Path(path).read_text())
    risk = _coerce(RiskConfig, raw.get("risk", {}))
    bt = raw.get("backtest", {})
    return risk, _coerce(BacktestConfig, {**bt, "risk": risk})
