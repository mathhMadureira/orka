import numpy as np

from vorcaro.quant.binary import (
    BinaryEncoder,
    BinaryPatternMiner,
    benjamini_hochberg,
    conditional_entropy_rate,
    gray,
    lempel_ziv_complexity,
)


def test_gray_code_neighbors_differ_by_one_bit():
    for i in range(15):
        assert bin(gray(i) ^ gray(i + 1)).count("1") == 1


def test_bh_reference():
    p = np.array([0.01, 0.04, 0.03, 0.005])
    assert np.allclose(benjamini_hochberg(p), [0.02, 0.04, 0.04, 0.02])


def planted(n=6000, seed=0, strength=0.75):
    """Bits aleatórios, mas após o padrão 1,1,0 a próxima barra sobe com prob `strength`."""
    rng = np.random.default_rng(seed)
    bits = rng.integers(0, 2, n)
    y = rng.standard_normal(n)
    for t in range(2, n - 1):
        if bits[t - 2] == 1 and bits[t - 1] == 1 and bits[t] == 0:
            up = rng.random() < strength
            y[t] = abs(y[t]) if up else -abs(y[t])
    return bits, y


def test_miner_finds_planted_pattern():
    bits, y = planted()
    m = BinaryPatternMiner(min_len=3, max_len=4).fit(bits, y)
    hit = m.patterns.get((1, 1, 0))
    assert hit is not None and hit.p_post > 0.65 and hit.q_value < 1e-6
    assert m.match(np.array([0, 1, 1, 0])) is not None


def test_miner_controls_false_discoveries():
    rng = np.random.default_rng(42)
    found = 0
    for _ in range(5):
        bits = rng.integers(0, 4, 4000)
        m = BinaryPatternMiner(max_len=5).fit(bits, rng.standard_normal(4000))
        found += len(m.patterns)
    assert found <= 2  # FDR 5%: em ruído puro quase nada sobrevive


def test_encoder_multibit_and_volume():
    rng = np.random.default_rng(5)
    r = rng.standard_normal(500)
    enc = BinaryEncoder(ret_bits=2, vol_bit=True).fit(r)
    s = enc.encode(r, rng.lognormal(size=500))
    assert s.min() >= 0 and s.max() < enc.alphabet == 8


def test_entropy_and_lz():
    rng = np.random.default_rng(6)
    rand = rng.integers(0, 2, 2000)
    periodic = np.tile([0, 1, 1], 700)
    assert conditional_entropy_rate(rand, 3, 2) > 0.97
    assert conditional_entropy_rate(periodic, 3, 2) < 0.05
    assert lempel_ziv_complexity(rand) > 0.85
    assert lempel_ziv_complexity(periodic) < 0.1
