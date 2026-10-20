"""Backtest orientado a eventos, barra a barra, sem look-ahead.

Linha do tempo de cada barra i:
    1. abertura_i  : executa a decisão tomada no fechamento de i−1 (preço = open_i ± slippage)
    2. durante i   : stops/alvos verificados com high_i/low_i (stop primeiro se ambos)
    3. fechamento_i: marca a mercado, atualiza risco, agentes aprendem com r_i,
                     conselho decide usando SOMENTE barras [0, i]
Zeragem obrigatória na última barra de cada dia (day trade) e após max_hold barras.
Saída também quando o conselho deixa de sustentar a posição (S·direção < exit_score).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from decimal import Decimal

import numpy as np

from ..agents.council import Council, Decision
from ..brokers.paper import PaperBroker
from ..core.models import Bar, Order, Side
from ..core.money import D
from ..data.series import Series
from ..quant import indicators as ind
from ..risk.manager import RiskConfig, RiskManager, TradePlan
from .metrics import Metrics, compute_metrics


@dataclass(frozen=True)
class BacktestConfig:
    cash: Decimal = Decimal("100000")
    fee_bps: float = 5.0
    slippage_bps: float = 2.0
    warmup: int = 300
    max_hold: int = 48
    flat_eod: bool = True
    exit_on_flip: bool = True
    exit_score: float = 0.05             # sai quando S·direção < exit_score (sinal decaiu)
    periods_per_year: float = 252 * 78       # barras de 5 min num pregão de 6,5 h
    lookback: int = 2500
    risk: RiskConfig = field(default_factory=RiskConfig)


@dataclass(frozen=True)
class Trade:
    symbol: str
    side: Side
    entry_i: int
    exit_i: int
    qty: Decimal
    entry: Decimal
    exit: Decimal
    pnl: Decimal                             # líquido de taxas
    reason: str


@dataclass
class BacktestResult:
    metrics: Metrics
    equity: np.ndarray
    trades: list[Trade]
    vetoes: dict[str, int]
    weights: dict[str, float]


def _bar(s: Series, i: int) -> Bar:
    return Bar(s.ts[i], s.open[i], s.high[i], s.low[i], s.close[i], s.volume[i])


def run_backtest(series: Series, council: Council, cfg: BacktestConfig = BacktestConfig()) -> BacktestResult:
    sym = series.symbol
    broker = PaperBroker(cfg.cash, cfg.fee_bps, cfg.slippage_bps)
    risk = RiskManager(cfg.risk)
    atr = ind.atr(series.high, series.low, series.close, 14)
    n = len(series)
    pending: TradePlan | None = None
    exit_next: str | None = None
    entry: dict | None = None
    trades: list[Trade] = []
    vetoes: dict[str, int] = {}
    equity = [float(cfg.cash)]
    in_market = 0
    fees_paid = Decimal(0)

    def close_trade(i: int, reason: str, px_fill_index: int = -1) -> None:
        nonlocal entry
        fill = broker.fills[px_fill_index]
        assert entry is not None
        fees = entry["fee"] + fill.fee
        gross = (fill.price - entry["price"]) * entry["qty"] * entry["side"].sign
        trades.append(Trade(sym, entry["side"], entry["i"], i, entry["qty"], entry["price"],
                            fill.price, gross - fees, reason))
        entry = None

    for i in range(cfg.warmup, n):
        bar = _bar(series, i)
        day = bar.ts.date()
        last_of_day = i == n - 1 or series.ts[i + 1].date() != day
        pos = broker.positions().get(sym)

        # 1. abertura: saídas pendentes e depois entradas pendentes
        broker.mark(sym, bar.open, bar.ts)
        if exit_next and pos is not None:
            broker.close_position(sym)
            fees_paid += broker.fills[-1].fee
            close_trade(i, exit_next)
            pos = None
        exit_next = None
        if pending is not None and pos is None:
            o = Order(sym, pending.side, pending.qty, stop_loss=pending.stop_loss,
                      take_profit=pending.take_profit)
            # recalcula stop/alvo relativos ao preço real de abertura (gap overnight/intrabar)
            shift = D(bar.open) - pending.entry
            o.stop_loss, o.take_profit = pending.stop_loss + shift, pending.take_profit + shift
            broker.submit(o)
            risk.record_order()
            f = broker.fills[-1]
            fees_paid += f.fee
            entry = {"i": i, "side": f.side, "qty": f.qty, "price": f.price, "fee": f.fee}
        pending = None

        # 2. intrabar: stops e alvos
        hit = broker.check_brackets(sym, bar)
        if hit is not None:
            fees_paid += hit.fee
            pos_closed_by = "stop" if (hit.price - entry["price"]) * entry["side"].sign < 0 else "alvo"
            close_trade(i, pos_closed_by)

        # 3. fechamento
        broker.mark(sym, bar.close, bar.ts)
        eq = broker.equity()
        equity.append(float(eq))
        risk.on_equity(eq, day)
        pos = broker.positions().get(sym)
        in_market += pos is not None

        r_i = math.log(series.close[i] / series.close[i - 1])
        council.learn(sym, r_i)

        if i == n - 1:
            break
        view = series.upto(i).tail(cfg.lookback)
        d: Decision = council.decide(view)

        if pos is not None:
            held = i - entry["i"] if entry else 0
            if cfg.flat_eod and last_of_day:
                exit_next = "fim do dia"
            elif held >= cfg.max_hold:
                exit_next = "tempo"
            elif cfg.exit_on_flip and d.score * (1 if pos.qty > 0 else -1) < cfg.exit_score:
                exit_next = "inversão" if abs(d.score) >= cfg.risk.min_score else "sinal decaiu"
            elif risk.halted:
                exit_next = "trava de risco"
            # o fill da saída acontece na abertura de i+1
            continue
        if cfg.flat_eod and last_of_day:
            continue  # não abre posição para carregar overnight

        plan = risk.plan(symbol=sym, score=d.score, agreement=d.agreement,
                         price=float(series.close[i]), atr=float(atr[i]), equity=eq,
                         open_positions=0)
        if isinstance(plan, str):
            key = re.split(r"[=:<≥(\d]", plan)[0].strip() or plan
            vetoes[key] = vetoes.get(key, 0) + 1
        else:
            pending = plan

    # encerra posição remanescente no último preço
    if broker.positions().get(sym) is not None:
        broker.close_position(sym)
        fees_paid += broker.fills[-1].fee
        close_trade(n - 1, "fim do teste")
        equity[-1] = float(broker.equity())

    span = max(1, n - cfg.warmup)
    m = compute_metrics(np.array(equity), [float(t.pnl) for t in trades], in_market / span,
                        float(fees_paid), cfg.periods_per_year)
    return BacktestResult(m, np.array(equity), trades, vetoes, dict(council.weights[sym]))


def walk_forward(series: Series, make_council, folds: int = 4,
                 cfg: BacktestConfig = BacktestConfig()) -> list[BacktestResult]:
    """Divide em blocos consecutivos; cada bloco é testado com agentes NOVOS que só veem
    o passado (warmup) daquele bloco. Estabilidade entre blocos > um backtest bonito."""
    n = len(series)
    size = (n - cfg.warmup) // folds
    out = []
    for k in range(folds):
        end = cfg.warmup + (k + 1) * size
        start = end - size - cfg.warmup
        seg = Series(series.symbol, *(a[start:end] for a in (series.ts, series.open, series.high,
                                                            series.low, series.close, series.volume)))
        out.append(run_backtest(seg, make_council(), cfg))
    return out
