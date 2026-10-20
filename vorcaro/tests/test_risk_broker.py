from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from vorcaro.brokers import PaperBroker, make_broker
from vorcaro.brokers.base import BrokerError
from vorcaro.core.models import Bar, Order, Side
from vorcaro.core.money import D
from vorcaro.risk import RiskConfig, RiskManager, TradePlan

EQ = Decimal("100000")


def plan(rm, **kw):
    args = dict(symbol="X", score=0.8, agreement=0.9, price=100.0, atr=1.0, equity=EQ,
                open_positions=0)
    args.update(kw)
    return rm.plan(**args)


def test_sizing_respects_risk_budget_and_caps():
    rm = RiskManager()
    p = plan(rm)
    assert isinstance(p, TradePlan) and p.side is Side.BUY
    assert p.risk_amount <= EQ * Decimal("0.005")          # risco até o stop ≤ 0,5%
    assert p.qty * p.entry <= EQ * Decimal("0.20")          # exposição ≤ 20%
    assert p.stop_loss == D("98.50") and p.take_profit == D("102.50")
    short = plan(rm, score=-0.8)
    assert short.side is Side.SELL and short.stop_loss > short.entry


@pytest.mark.parametrize("kw,reason", [
    ({"score": 0.05}, "|S|"), ({"agreement": 0.3}, "acordo"), ({"open_positions": 5}, "máximo"),
    ({"atr": 0.0}, "ATR"),
])
def test_vetoes(kw, reason):
    assert reason in plan(RiskManager(), **kw)


def test_kill_switches():
    rm = RiskManager(RiskConfig())
    rm.on_equity(EQ, date(2024, 1, 1))
    rm.on_equity(EQ * Decimal("0.979"), date(2024, 1, 1))
    assert rm.halted and "perda diária" in plan(rm)
    rm.on_equity(EQ * Decimal("0.979"), date(2024, 1, 2))   # novo dia libera
    assert not rm.halted
    rm.on_equity(EQ * Decimal("0.89"), date(2024, 1, 3))
    assert "drawdown" in rm.halted_reason
    rm.on_equity(EQ, date(2024, 1, 4))                      # drawdown NÃO libera sozinho
    assert rm.halted


def test_paper_broker_exact_accounting():
    b = PaperBroker("10000", fee_bps=10, slippage_bps=0)
    b.mark("X", "100")
    b.submit(Order("X", Side.BUY, D("10")))
    assert b.cash() == D("10000") - D("1000") - D("1.0")
    b.mark("X", "110")
    assert b.equity() == D("10099.0")
    b.close_position("X")
    assert b.cash() == D("10000") - D("1") + D("100") - D("1.1")
    assert b.positions() == {}


def test_bracket_stop_has_priority_over_target():
    b = PaperBroker("10000", fee_bps=0, slippage_bps=0)
    b.mark("X", "100")
    b.submit(Order("X", Side.BUY, D("1"), stop_loss=D("98"), take_profit=D("102")))
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    f = b.check_brackets("X", Bar(ts, 100, 103, 97, 101, 1))   # tocou os dois
    assert f.price == D("98")


def test_gap_through_stop_fills_at_open():
    b = PaperBroker("10000", fee_bps=0, slippage_bps=0)
    b.mark("X", "100")
    b.submit(Order("X", Side.BUY, D("1"), stop_loss=D("98"), take_profit=D("102")))
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert b.check_brackets("X", Bar(ts, 95, 96, 94, 95, 1)).price == D("95")


def test_live_requires_double_lock(monkeypatch):
    monkeypatch.delenv("VORCARO_LIVE", raising=False)
    with pytest.raises(BrokerError):
        make_broker("paper", live_flag=True)
    assert make_broker("paper").live is False
