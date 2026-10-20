"""Mineração de padrões em dados binários.

Ideia: transformar o mercado em um fluxo de bits e procurar sequências cuja próxima barra é
estatisticamente previsível — sem se enganar com o problema das comparações múltiplas.

Codificação (por barra t):
    bits de retorno  : quantil do log-retorno em 2^ret_bits faixas, em código Gray
                       (faixas vizinhas diferem em 1 bit => padrões "próximos" ficam próximos)
                       com ret_bits=1 o bit é simplesmente 1 se r_t > 0
    bit de volume    : 1 se volume_t > mediana móvel do volume (participação acima do normal)
    símbolo s_t      = (gray(q_t) << vol_bit) | v_t   ∈ {0, …, 2^(ret_bits+vol_bit) − 1}

Uma *palavra* de comprimento L é a tupla (s_{t-L+1}, …, s_t). Para cada palavra contamos
n (ocorrências) e k (vezes em que r_{t+1} > 0) e testamos H0: p = p_base com teste
binomial exato. O conjunto de p-valores de TODAS as palavras testadas passa pelo
procedimento de Benjamini-Hochberg para controlar a FDR em alpha. Só sobrevivem padrões
com suporte mínimo e q-valor < alpha. A probabilidade usada para operar é a média da
posterior Beta (encolhida para p_base), não a frequência crua.

Na previsão usamos *back-off* de ordem variável: a palavra mais longa significativa que
casa com o final da sequência recente vence (estilo modelo de Markov de ordem variável).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .stats import beta_posterior, binom_test_two_sided, shannon_entropy


def gray(n: int) -> int:
    return n ^ (n >> 1)


@dataclass(frozen=True)
class PatternStat:
    word: tuple[int, ...]
    n: int
    k: int
    mean_ret: float
    p_value: float
    q_value: float
    p_post: float

    @property
    def edge(self) -> float:
        """Vantagem direcional em [-1, 1]: 2p − 1."""
        return 2.0 * self.p_post - 1.0

    def bits(self, bits_per_symbol: int) -> str:
        return " ".join(format(s, f"0{bits_per_symbol}b") for s in self.word)


@dataclass
class BinaryEncoder:
    ret_bits: int = 1
    vol_bit: bool = True
    vol_window: int = 20
    _edges: np.ndarray | None = field(default=None, repr=False)

    @property
    def bits_per_symbol(self) -> int:
        return self.ret_bits + int(self.vol_bit)

    @property
    def alphabet(self) -> int:
        return 1 << self.bits_per_symbol

    def fit(self, returns: np.ndarray) -> "BinaryEncoder":
        if self.ret_bits > 1:
            qs = np.linspace(0, 1, (1 << self.ret_bits) + 1)[1:-1]
            self._edges = np.quantile(returns[np.isfinite(returns)], qs)
        return self

    def encode(self, returns: np.ndarray, volume: np.ndarray | None = None) -> np.ndarray:
        r = np.asarray(returns, dtype=float)
        if self.ret_bits == 1:
            q = (r > 0).astype(int)
        else:
            if self._edges is None:
                raise RuntimeError("chame fit() antes de encode() com ret_bits > 1")
            q = np.searchsorted(self._edges, r, side="right")
        sym = np.vectorize(gray)(q) if self.ret_bits > 1 else q
        if self.vol_bit:
            if volume is None:
                raise ValueError("vol_bit=True exige volume")
            v = np.asarray(volume, dtype=float)
            med = _rolling_median_causal(v, self.vol_window)
            vb = (v > med).astype(int)
            sym = (sym << 1) | vb
        return sym.astype(int)


def _rolling_median_causal(v: np.ndarray, n: int) -> np.ndarray:
    """Mediana das n barras ANTERIORES (exclui t para não vazar informação)."""
    out = np.full(len(v), np.inf)
    for i in range(1, min(n, len(v))):
        out[i] = np.median(v[:i])
    if len(v) > n:
        out[n:] = np.median(np.lib.stride_tricks.sliding_window_view(v[:-1], n), axis=1)
    return out


def benjamini_hochberg(p: np.ndarray) -> np.ndarray:
    p = np.asarray(p, dtype=float)
    m = len(p)
    if m == 0:
        return p
    order = np.argsort(p)
    ranked = p[order] * m / np.arange(1, m + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.clip(q, 0, 1)
    return out


@dataclass
class BinaryPatternMiner:
    min_len: int = 2
    max_len: int = 6
    min_support: int = 30
    alpha: float = 0.05
    prior_strength: float = 20.0       # pseudo-observações da priori Beta centrada em p_base
    patterns: dict[tuple[int, ...], PatternStat] = field(default_factory=dict)
    base_rate: float = 0.5
    tested: int = 0

    def fit(self, symbols: np.ndarray, next_returns: np.ndarray) -> "BinaryPatternMiner":
        """symbols[t] descreve a barra t; next_returns[t] = r_{t+1} (alvo)."""
        s = np.asarray(symbols, dtype=int)
        y = np.asarray(next_returns, dtype=float)
        if len(s) != len(y):
            raise ValueError("symbols e next_returns devem ter o mesmo tamanho")
        valid = np.isfinite(y)
        ups = (y > 0) & valid
        self.base_rate = float(ups.sum() / max(1, valid.sum()))
        raw: list[tuple[tuple[int, ...], int, int, float]] = []
        for L in range(self.min_len, self.max_len + 1):
            buckets: dict[tuple[int, ...], list[int]] = {}
            for t in range(L - 1, len(s)):
                if not valid[t]:
                    continue
                buckets.setdefault(tuple(s[t - L + 1: t + 1]), []).append(t)
            for w, idx in buckets.items():
                if len(idx) < self.min_support:
                    continue
                ii = np.asarray(idx)
                raw.append((w, len(ii), int(ups[ii].sum()), float(y[ii].mean())))
        self.tested = len(raw)
        if not raw:
            self.patterns = {}
            return self
        pvals = np.array([binom_test_two_sided(k, n, self.base_rate) for _, n, k, _ in raw])
        qvals = benjamini_hochberg(pvals)
        a0 = self.prior_strength * self.base_rate
        b0 = self.prior_strength * (1 - self.base_rate)
        self.patterns = {}
        for (w, n, k, mr), p, q in zip(raw, pvals, qvals, strict=True):
            if q < self.alpha:
                post, _ = beta_posterior(k, n, a0, b0)
                self.patterns[w] = PatternStat(w, n, k, mr, float(p), float(q), post)
        return self

    def match(self, recent: np.ndarray) -> PatternStat | None:
        """Padrão significativo mais longo que casa com o final da sequência recente."""
        recent = np.asarray(recent, dtype=int)
        for L in range(min(self.max_len, len(recent)), self.min_len - 1, -1):
            hit = self.patterns.get(tuple(recent[-L:]))
            if hit is not None:
                return hit
        return None

    def top(self, k: int = 10) -> list[PatternStat]:
        return sorted(self.patterns.values(), key=lambda p: (p.q_value, -abs(p.edge)))[:k]


def conditional_entropy_rate(symbols: np.ndarray, order: int, alphabet: int) -> float:
    """H(X_t | X_{t-order..t-1}) normalizada em [0,1] (1 = imprevisível).

    Usa correção de Miller-Madow por contexto: Ĥ = Ĥ_ML + (m_c − 1) / (2 n_c), em nats,
    onde m_c é o número de símbolos observados no contexto c.
    """
    s = np.asarray(symbols, dtype=int)
    if len(s) <= order + 1 or alphabet < 2:
        return 1.0
    if order == 0:
        return shannon_entropy(s, base=alphabet)
    ctx_counts: dict[tuple[int, ...], np.ndarray] = {}
    for t in range(order, len(s)):
        c = tuple(s[t - order: t])
        arr = ctx_counts.setdefault(c, np.zeros(alphabet))
        arr[s[t]] += 1
    total = len(s) - order
    h = 0.0
    for arr in ctx_counts.values():
        nc = arr.sum()
        p = arr[arr > 0] / nc
        h_ml = float(-(p * np.log(p)).sum())
        h += nc / total * (h_ml + (len(p) - 1) / (2 * nc))
    return min(1.0, h / math.log(alphabet))


def lempel_ziv_complexity(bits: np.ndarray) -> float:
    """Complexidade LZ76 normalizada (≈1 para sequência aleatória, →0 para regular)."""
    b = "".join(str(int(x)) for x in bits)
    n = len(b)
    if n < 2:
        return 1.0
    i, c, k, l, k_max = 0, 1, 1, 1, 1
    while True:
        if b[i + k - 1] == b[l + k - 1]:
            k += 1
            if l + k > n:
                c += 1
                break
        else:
            k_max = max(k, k_max)
            i += 1
            if i == l:
                c += 1
                l += k_max
                if l + 1 > n:
                    break
                i, k, k_max = 0, 1, 1
            else:
                k = 1
    return c * math.log2(n) / n
