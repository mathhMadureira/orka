import math

import numpy as np
import pytest

from vorcaro.quant import indicators as ind
from vorcaro.quant import stats as st
from vorcaro.quant.equation import omega


def test_sma_ema_known_values():
    x = np.arange(1, 11, dtype=float)
    assert np.allclose(ind.sma(x, 3)[2:], np.arange(2, 10))
    e = ind.ema(x, 3)
    assert math.isnan(e[1]) and e[2] == 2.0
    assert e[3] == pytest.approx(0.5 * 4 + 0.5 * 2)


def test_rsi_extremes_and_range():
    up = np.arange(1, 50, dtype=float)
    assert ind.rsi(up, 14)[-1] == 100.0
    rng = np.random.default_rng(0)
    r = ind.rsi(100 + rng.standard_normal(500).cumsum(), 14)
    v = r[np.isfinite(r)]
    assert v.min() >= 0 and v.max() <= 100


def test_atr_constant_range():
    h, l, c = np.full(30, 11.0), np.full(30, 9.0), np.full(30, 10.0)
    assert ind.atr(h, l, c, 14)[-1] == pytest.approx(2.0)


def test_indicators_are_causal():
    rng = np.random.default_rng(1)
    x = 100 + rng.standard_normal(300).cumsum()
    y = x.copy()
    y[200:] += 50  # mudar o futuro não pode alterar o passado
    for f in (lambda a: ind.ema(a, 10), lambda a: ind.rsi(a, 14), lambda a: ind.zscore(a, 20)):
        assert np.allclose(f(x)[:200], f(y)[:200], equal_nan=True)


def test_norm_roundtrip():
    for x in (-5, -2.5, -0.3, 0, 0.7, 3.1):
        assert st.norm_ppf(st.norm_cdf(x)) == pytest.approx(x, abs=1e-9)
    assert st.norm_ppf(0.975) == pytest.approx(1.959963984540054, abs=1e-12)


def test_binom_test_matches_reference():
    assert st.binom_test_two_sided(7, 10, 0.5) == pytest.approx(0.34375)
    assert st.binom_test_two_sided(60, 100, 0.5) == pytest.approx(0.056887933640980784, rel=1e-9)


def test_hurst_regimes():
    rng = np.random.default_rng(3)
    white = rng.standard_normal(2048)
    assert abs(st.hurst_rs(white) - 0.5) < 0.08
    persistent = np.empty(2048)
    persistent[0] = 0
    for i in range(1, 2048):
        persistent[i] = 0.6 * persistent[i - 1] + white[i]
    anti = np.empty(2048)
    anti[0] = 0
    for i in range(1, 2048):
        anti[i] = -0.6 * anti[i - 1] + white[i]
    # AR(1) tem memória curta: Hurst se afasta de 0.5 nas escalas finitas, sem chegar a extremos
    assert st.hurst_rs(persistent) > 0.55
    assert st.hurst_rs(anti) < 0.45


def test_kelly_and_psr():
    assert st.kelly_fraction(0.6, 1.0) == pytest.approx(0.2)
    assert st.kelly_fraction(0.4, 1.0) == 0.0
    rng = np.random.default_rng(4)
    assert st.probabilistic_sharpe(rng.normal(0.001, 0.01, 2000)) > 0.95
    assert st.probabilistic_sharpe(rng.normal(-0.001, 0.01, 2000)) < 0.05


def test_kalman_tracks_level():
    k = st.Kalman1D(q=1e-4, r=1e-2)
    out = k.filter(np.r_[np.zeros(50), np.ones(200)])
    assert abs(out[-1] - 1) < 0.01


def test_max_drawdown():
    assert st.max_drawdown(np.array([100, 120, 90, 130])) == pytest.approx(-0.25)


def test_omega_bounded_and_explained(rw):
    r = omega(rw.tail(400))
    assert -1 <= r.omega <= 1 and 0 <= r.entropy <= 1 and 0 <= r.alpha <= 1
    assert "Ω=" in r.explain()
