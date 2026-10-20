r"""Agente de risco: tem poder de VETO sobre qualquer decisão.

Dimensionamento (risco fixo fracionário, limitado por Kelly fracionário):

    stop       = k_SL · ATR             alvo = k_TP · ATR       (razão b = k_TP / k_SL)
    risco R$   = equity · r_trade · |S|                        (convicção escala o risco)
    qtd        = risco R$ / stop
    p̂          = ½ + ½ · |S| · agreement · shrink               (probabilidade conservadora)
    f_Kelly    = p̂ − (1 − p̂) / b ;  exposição ≤ φ · f_Kelly · equity  (φ = fração de Kelly)
    exposição  ≤ max_position_pct · equity

Travas (kill switches): perda diária máxima, drawdown máximo desde o pico, número máximo
de posições, limite de ordens por dia, e lista de símbolos bloqueados.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from ..core.models import Side
from ..core.money import D, quantize_down, quantize_price
from ..quant.stats import kelly_fraction


@dataclass(frozen=True)
class RiskConfig:
    risk_per_trade: Decimal = Decimal("0.005")       # 0,5% do patrimônio por trade
    max_position_pct: Decimal = Decimal("0.20")
    max_daily_loss_pct: Decimal = Decimal("0.02")
    max_drawdown_pct: Decimal = Decimal("0.10")
    max_open_positions: int = 5
    max_orders_per_day: int = 50
    sl_atr: float = 1.5
    tp_atr: float = 2.5
    kelly_fraction: float = 0.25
    probability_shrink: float = 0.3
    min_score: float = 0.15
    min_agreement: float = 0.6
    allow_short: bool = True
    blocked: frozenset[str] = frozenset()


@dataclass(frozen=True)
class TradePlan:
    symbol: str
    side: Side
    qty: Decimal
    entry: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    risk_amount: Decimal
    reason: str


@dataclass
class RiskManager:
    config: RiskConfig = field(default_factory=RiskConfig)
    peak_equity: Decimal = Decimal(0)
    day: date | None = None
    day_start_equity: Decimal = Decimal(0)
    orders_today: int = 0
    halted_reason: str | None = None

    def on_equity(self, equity: Decimal, today: date) -> None:
        if self.day != today:
            self.day, self.day_start_equity, self.orders_today = today, equity, 0
            if self.halted_reason and self.halted_reason.startswith("perda diária"):
                self.halted_reason = None
        self.peak_equity = max(self.peak_equity, equity)
        c = self.config
        if self.day_start_equity > 0:
            dl = (self.day_start_equity - equity) / self.day_start_equity
            if dl >= c.max_daily_loss_pct:
                self.halted_reason = f"perda diária {dl:.2%} ≥ {c.max_daily_loss_pct:.2%}"
        if self.peak_equity > 0:
            dd = (self.peak_equity - equity) / self.peak_equity
            if dd >= c.max_drawdown_pct:
                self.halted_reason = f"drawdown {dd:.2%} ≥ {c.max_drawdown_pct:.2%} (requer reset manual)"

    @property
    def halted(self) -> bool:
        return self.halted_reason is not None

    def plan(self, *, symbol: str, score: float, agreement: float, price: float, atr: float,
             equity: Decimal, open_positions: int, lot_step: Decimal = Decimal("0.00000001"),
             tick: Decimal = Decimal("0.01")) -> TradePlan | str:
        """Retorna um TradePlan ou o motivo do veto (str)."""
        c = self.config
        if self.halted:
            return f"travado: {self.halted_reason}"
        if symbol in c.blocked:
            return "símbolo bloqueado"
        if abs(score) < c.min_score:
            return f"|S|={abs(score):.3f} < {c.min_score}"
        if agreement < c.min_agreement:
            return f"acordo {agreement:.0%} < {c.min_agreement:.0%}"
        if score < 0 and not c.allow_short:
            return "venda a descoberto desabilitada"
        if open_positions >= c.max_open_positions:
            return "máximo de posições abertas"
        if self.orders_today >= c.max_orders_per_day:
            return "limite diário de ordens"
        if not (atr > 0 and price > 0):
            return "ATR/preço inválido"

        side = Side.BUY if score > 0 else Side.SELL
        px, a = D(price), D(atr)
        stop_dist = a * D(c.sl_atr)
        b = c.tp_atr / c.sl_atr
        risk_amt = equity * c.risk_per_trade * D(abs(score))
        qty = risk_amt / stop_dist

        p_hat = 0.5 + 0.5 * abs(score) * agreement * c.probability_shrink
        f = kelly_fraction(p_hat, b) * c.kelly_fraction
        if f <= 0:
            return f"sem vantagem por Kelly (p̂={p_hat:.3f}, b={b:.2f})"
        cap = min(D(f), c.max_position_pct) * equity / px
        qty = quantize_down(min(qty, cap), lot_step)
        if qty <= 0:
            return "quantidade abaixo do lote mínimo"

        sl = quantize_price(px - side.sign * stop_dist, tick)
        tp = quantize_price(px + side.sign * a * D(c.tp_atr), tick)
        return TradePlan(symbol, side, qty, px, sl, tp, qty * stop_dist,
                         f"S={score:+.3f} p̂={p_hat:.3f} f={f:.4f} b={b:.2f}")

    def record_order(self) -> None:
        self.orders_today += 1

    def reset(self) -> None:
        self.halted_reason = None
