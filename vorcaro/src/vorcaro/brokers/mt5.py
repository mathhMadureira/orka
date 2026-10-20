"""B3 via MetaTrader 5 (XP, Clear, Rico, Genial, BTG, Modal...). Requer Windows + terminal MT5.

Fora do modo live, só aceita conectar em conta DEMO (trade_mode == 0).
Stops e alvos são enviados no próprio order_send (proteção no servidor).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal

import numpy as np

from ..core.models import Order, OrderStatus, OrderType, Position, Side
from ..core.money import D
from ..data.series import Series
from .base import Broker, BrokerError, Instrument


class MT5Broker(Broker):
    name = "mt5"

    def __init__(self, *, live: bool = False):
        try:
            import MetaTrader5 as mt5  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise BrokerError("instale com: pip install 'vorcaro[b3]' (somente Windows)") from e
        self.mt5 = mt5
        ok = mt5.initialize(login=int(os.getenv("VORCARO_MT5_LOGIN", "0")),
                            password=os.getenv("VORCARO_MT5_PASSWORD", ""),
                            server=os.getenv("VORCARO_MT5_SERVER", ""))
        if not ok:
            raise BrokerError(f"MT5 initialize falhou: {mt5.last_error()}")
        info = mt5.account_info()
        if not live and info.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
            mt5.shutdown()
            raise BrokerError("conta REAL detectada sem --live; use uma conta demo ou ative o modo live")
        self.live = live

    def equity(self) -> Decimal:
        return D(self.mt5.account_info().equity)

    def cash(self) -> Decimal:
        return D(self.mt5.account_info().margin_free)

    def positions(self) -> dict[str, Position]:
        out: dict[str, Position] = {}
        for p in self.mt5.positions_get() or []:
            sign = 1 if p.type == self.mt5.POSITION_TYPE_BUY else -1
            out[p.symbol] = Position(p.symbol, D(p.volume) * sign, D(p.price_open),
                                     stop_loss=D(p.sl) if p.sl else None,
                                     take_profit=D(p.tp) if p.tp else None)
        return out

    def instrument(self, symbol: str) -> Instrument:
        i = self.mt5.symbol_info(symbol)
        if i is None:
            raise BrokerError(f"símbolo {symbol} não encontrado no MT5")
        self.mt5.symbol_select(symbol, True)
        return Instrument(symbol, D(i.volume_step), D(i.trade_tick_size))

    def submit(self, order: Order) -> Order:
        m = self.mt5
        tick = m.symbol_info_tick(order.symbol)
        buy = order.side is Side.BUY
        req = {
            "action": m.TRADE_ACTION_DEAL if order.type is OrderType.MARKET else m.TRADE_ACTION_PENDING,
            "symbol": order.symbol, "volume": float(order.qty),
            "type": (m.ORDER_TYPE_BUY if buy else m.ORDER_TYPE_SELL) if order.type is OrderType.MARKET
                    else (m.ORDER_TYPE_BUY_LIMIT if buy else m.ORDER_TYPE_SELL_LIMIT),
            "price": float(order.limit_price) if order.limit_price else (tick.ask if buy else tick.bid),
            "deviation": 10, "magic": 7_700_001, "comment": order.client_id[:31],
            "type_time": m.ORDER_TIME_DAY, "type_filling": m.ORDER_FILLING_RETURN,
        }
        if order.stop_loss is not None:
            req["sl"] = float(order.stop_loss)
        if order.take_profit is not None:
            req["tp"] = float(order.take_profit)
        r = m.order_send(req)
        if r is None or r.retcode != m.TRADE_RETCODE_DONE:
            order.status = OrderStatus.REJECTED
            raise BrokerError(f"MT5 rejeitou: {getattr(r, 'retcode', None)} {getattr(r, 'comment', '')}")
        order.broker_id = str(r.order)
        order.status = OrderStatus.FILLED
        return order

    def cancel(self, order: Order) -> None:
        if order.broker_id:
            self.mt5.order_send({"action": self.mt5.TRADE_ACTION_REMOVE, "order": int(order.broker_id)})
            order.status = OrderStatus.CANCELED

    def bars(self, symbol: str, timeframe: str = "5m", limit: int = 500) -> Series:
        m = self.mt5
        tf = {"1m": m.TIMEFRAME_M1, "5m": m.TIMEFRAME_M5, "15m": m.TIMEFRAME_M15,
              "1h": m.TIMEFRAME_H1, "1d": m.TIMEFRAME_D1}[timeframe]
        r = m.copy_rates_from_pos(symbol, tf, 0, limit)
        if r is None or len(r) == 0:
            raise BrokerError(f"sem barras para {symbol}")
        ts = np.array([datetime.fromtimestamp(int(t), timezone.utc) for t in r["time"]], dtype=object)
        return Series(symbol, ts, r["open"].astype(float), r["high"].astype(float),
                      r["low"].astype(float), r["close"].astype(float),
                      r["real_volume"].astype(float))
