from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np

from ..quant.stats import max_drawdown, probabilistic_sharpe, sharpe


@dataclass(frozen=True)
class Metrics:
    total_return: float
    sharpe: float
    sortino: float
    max_drawdown: float
    psr: float                   # P(Sharpe verdadeiro > 0)
    trades: int
    win_rate: float
    profit_factor: float
    avg_trade: float
    exposure: float
    fees: float

    def as_dict(self) -> dict:
        return asdict(self)

    def report(self) -> str:
        pf = "∞" if math.isinf(self.profit_factor) else f"{self.profit_factor:.2f}"
        return (f"retorno {self.total_return:+.2%} | Sharpe {self.sharpe:.2f} | Sortino "
                f"{self.sortino:.2f} | MaxDD {self.max_drawdown:.2%} | PSR {self.psr:.1%} | "
                f"trades {self.trades} | acerto {self.win_rate:.1%} | PF {pf} | "
                f"médio {self.avg_trade:+.2f} | exposição {self.exposure:.1%} | taxas {self.fees:.2f}")


def compute_metrics(equity: np.ndarray, trade_pnls: list[float], exposure: float, fees: float,
                    periods_per_year: float) -> Metrics:
    e = np.asarray(equity, dtype=float)
    r = np.diff(e) / e[:-1] if len(e) > 1 else np.zeros(0)
    downside = r[r < 0]
    dd_std = math.sqrt((downside ** 2).mean()) if len(downside) else 0.0
    sortino = (r.mean() / dd_std * math.sqrt(periods_per_year)) if dd_std > 0 else 0.0
    wins = [p for p in trade_pnls if p > 0]
    losses = [-p for p in trade_pnls if p < 0]
    pf = (sum(wins) / sum(losses)) if losses else (math.inf if wins else 0.0)
    return Metrics(
        total_return=float(e[-1] / e[0] - 1) if len(e) else 0.0,
        sharpe=sharpe(r, periods_per_year),
        sortino=float(sortino),
        max_drawdown=max_drawdown(e),
        psr=probabilistic_sharpe(r),
        trades=len(trade_pnls),
        win_rate=len(wins) / len(trade_pnls) if trade_pnls else 0.0,
        profit_factor=float(pf),
        avg_trade=float(np.mean(trade_pnls)) if trade_pnls else 0.0,
        exposure=exposure,
        fees=fees,
    )
