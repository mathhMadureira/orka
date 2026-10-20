"""Aritmética monetária exata.

Todo valor que representa dinheiro, quantidade ou preço de ordem passa por ``Decimal``.
Floats ficam restritos ao cálculo de sinais (onde ruído de 1e-16 é irrelevante); a
contabilidade (caixa, PnL, taxas) nunca acumula erro binário de ponto flutuante.
"""

from __future__ import annotations

from decimal import ROUND_DOWN, ROUND_HALF_EVEN, Decimal, getcontext

getcontext().prec = 34  # precisão de decimal128 (IEEE 754-2008)


def D(x: object) -> Decimal:
    """Converte para Decimal sem herdar o erro binário do float (usa repr curto)."""
    if isinstance(x, Decimal):
        return x
    if hasattr(x, "dtype") and getattr(x.dtype, "kind", "") == "f":
        x = float(x)
    if isinstance(x, float):
        return Decimal(repr(float(x)))  # float(x) normaliza np.float64
    return Decimal(str(x))


def quantize_down(qty: Decimal, step: Decimal) -> Decimal:
    """Arredonda a quantidade para baixo ao múltiplo do lote mínimo (nunca excede o risco)."""
    if step <= 0:
        return qty
    return (qty / step).to_integral_value(rounding=ROUND_DOWN) * step


def quantize_price(price: Decimal, tick: Decimal) -> Decimal:
    """Arredonda o preço ao tick da bolsa (banker's rounding)."""
    if tick <= 0:
        return price
    return (price / tick).to_integral_value(rounding=ROUND_HALF_EVEN) * tick
