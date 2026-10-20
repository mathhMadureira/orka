from datetime import datetime, timezone
from decimal import Decimal

import numpy as np
import pytest

from vorcaro.core.models import Fill, Position, Side, Signal
from vorcaro.core.money import D, quantize_down, quantize_price

NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def fill(side, qty, px, fee="0"):
    return Fill("x", "S", side, D(qty), D(px), D(fee), NOW)


def test_decimal_is_exact():
    assert D(0.1) + D(0.2) == Decimal("0.3")
    assert D(np.float64(0.1)) == Decimal("0.1")
    assert sum([D("0.01")] * 100) == Decimal("1.00")


def test_quantize():
    assert quantize_down(D("1.23456789"), D("0.001")) == D("1.234")
    assert quantize_down(D("0.0009"), D("0.001")) == 0
    assert quantize_price(D("10.005"), D("0.01")) == D("10.00")  # banker's
    assert quantize_price(D("10.015"), D("0.01")) == D("10.02")


def test_position_average_and_realized():
    p = Position("S")
    p.apply(fill(Side.BUY, 10, 100))
    p.apply(fill(Side.BUY, 10, 110))
    assert p.avg_price == D(105) and p.qty == 20
    r = p.apply(fill(Side.SELL, 5, 120))
    assert r == D(75) and p.qty == 15 and p.avg_price == D(105)
    r = p.apply(fill(Side.SELL, 25, 100))  # zera e vira vendido 10 @ 100
    assert r == D(-75) and p.qty == -10 and p.avg_price == D(100)
    assert p.unrealized(D(90)) == D(100)


def test_signal_bounds():
    with pytest.raises(ValueError):
        Signal("a", "S", 1.5, 0.5)
    assert Signal("a", "S", -0.5, 0.5).strength == -0.25
