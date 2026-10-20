"""Motor ao vivo: ciclo scan → decisão → risco → execução → auditoria.

Cada ciclo:
  1. busca barras de cada ativo do universo (somente barras FECHADAS)
  2. agentes aprendem com o retorno realizado desde a última decisão
  3. scanner ranqueia oportunidades; risco aprova/veta e dimensiona
  4. execução envia ordens (com stop/alvo); stops do lado cliente são vigiados aqui
  5. tudo vai para um diário JSONL (auditoria e reprodutibilidade)
"""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from datetime import time as dtime
from decimal import Decimal
from pathlib import Path
from typing import Callable

from ..agents.council import Council
from ..agents.scanner import ScannerAgent
from ..brokers.base import Broker, BrokerError
from ..core.models import Order
from ..core.money import D
from ..data.series import Series
from ..quant import indicators as ind
from ..risk.manager import RiskManager, TradePlan

log = logging.getLogger("vorcaro.live")


@dataclass
class LiveConfig:
    universe: list[str]
    timeframe: str = "5m"
    bars: int = 1500
    interval_s: int = 300
    top_n: int = 3
    session_close_utc: dtime | None = None    # ex.: 20:45 para zerar antes do fechamento
    dry_run: bool = True
    journal: Path = Path("state/journal.jsonl")


@dataclass
class LiveEngine:
    broker: Broker
    council: Council
    risk: RiskManager
    cfg: LiveConfig
    data_fn: Callable[[str], Series] | None = None
    _last_close: dict[str, float] = field(default_factory=dict)
    _stops: dict[str, tuple[Decimal, Decimal, int]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.scanner = ScannerAgent(self.council)
        self.cfg.journal.parent.mkdir(parents=True, exist_ok=True)

    def _journal(self, kind: str, **data) -> None:
        rec = {"ts": datetime.now(timezone.utc).isoformat(), "kind": kind, **data}
        with self.cfg.journal.open("a") as fh:
            fh.write(json.dumps(rec, default=str, ensure_ascii=False) + "\n")

    def _series(self, symbol: str) -> Series:
        s = self.data_fn(symbol) if self.data_fn else self.broker.bars(symbol, self.cfg.timeframe,
                                                                       self.cfg.bars)
        # descarta a barra em formação (o último candle ainda não fechou)
        return s.upto(len(s) - 2) if len(s) > 1 else s

    def cycle(self) -> list[TradePlan]:
        now = datetime.now(timezone.utc)
        eq = self.broker.equity()
        self.risk.on_equity(eq, now.date())
        positions = self.broker.positions()
        universe: list[Series] = []
        for sym in self.cfg.universe:
            try:
                s = self._series(sym)
            except (BrokerError, OSError, ValueError) as e:
                log.warning("dados indisponíveis para %s: %s", sym, e)
                continue
            if hasattr(self.broker, "mark"):
                self.broker.mark(sym, s.close[-1], s.ts[-1])
            prev = self._last_close.get(sym)
            if prev:
                self.council.learn(sym, math.log(s.close[-1] / prev))
            self._last_close[sym] = float(s.close[-1])
            self._client_side_stops(sym, s, positions)
            universe.append(s)

        if self.cfg.session_close_utc and now.time() >= self.cfg.session_close_utc:
            for sym in list(self.broker.positions()):
                self._execute_close(sym, "fim do pregão")
            return []
        if self.risk.halted:
            log.error("TRAVADO: %s", self.risk.halted_reason)
            self._journal("halt", reason=self.risk.halted_reason)
            for sym in list(self.broker.positions()):
                self._execute_close(sym, "trava de risco")
            return []

        plans: list[TradePlan] = []
        ops = self.scanner.scan(universe, top=self.cfg.top_n)
        by_sym = {s.symbol: s for s in universe}
        for op in ops:
            self._journal("opportunity", symbol=op.symbol, score=op.score,
                          decision=op.decision.explain())
            if op.symbol in positions:
                continue
            s = by_sym[op.symbol]
            a = float(ind.atr(s.high, s.low, s.close, 14)[-1])
            inst = self.broker.instrument(op.symbol)
            plan = self.risk.plan(symbol=op.symbol, score=op.decision.score,
                                  agreement=op.decision.agreement, price=float(s.close[-1]),
                                  atr=a, equity=eq, open_positions=len(positions) + len(plans),
                                  lot_step=inst.lot_step, tick=inst.tick)
            if isinstance(plan, str):
                self._journal("veto", symbol=op.symbol, reason=plan)
                continue
            if inst.min_notional and plan.qty * plan.entry < inst.min_notional:
                self._journal("veto", symbol=op.symbol, reason="abaixo do notional mínimo")
                continue
            plans.append(plan)
            self._execute(plan)
        return plans

    def _execute(self, plan: TradePlan) -> None:
        self._journal("plan", dry_run=self.cfg.dry_run, **asdict(plan))
        log.info("%s %s %s @ %s SL %s TP %s | %s", "SIMULAÇÃO" if self.cfg.dry_run else "ORDEM",
                 plan.side.value, plan.qty, plan.entry, plan.stop_loss, plan.take_profit, plan.reason)
        if self.cfg.dry_run:
            return
        o = Order(plan.symbol, plan.side, plan.qty, stop_loss=plan.stop_loss,
                  take_profit=plan.take_profit)
        try:
            self.broker.submit(o)
            self.risk.record_order()
            self._stops[plan.symbol] = (plan.stop_loss, plan.take_profit, plan.side.sign)
            self._journal("order", symbol=o.symbol, id=o.broker_id, status=o.status.value)
        except BrokerError as e:
            log.error("ordem rejeitada: %s", e)
            self._journal("reject", symbol=plan.symbol, error=str(e))

    def _execute_close(self, sym: str, reason: str) -> None:
        self._journal("close", symbol=sym, reason=reason, dry_run=self.cfg.dry_run)
        if not self.cfg.dry_run:
            try:
                self.broker.close_position(sym)
            except BrokerError as e:
                log.error("falha ao zerar %s: %s", sym, e)
        self._stops.pop(sym, None)

    def _client_side_stops(self, sym: str, s: Series, positions: dict) -> None:
        """Para corretoras sem bracket nativo (spot cripto): vigia stop/alvo pelo último candle."""
        if sym not in self._stops or sym not in positions:
            return
        sl, tp, sign = self._stops[sym]
        lo, hi = D(s.low[-1]), D(s.high[-1])
        if (sign > 0 and lo <= sl) or (sign < 0 and hi >= sl):
            self._execute_close(sym, "stop")
        elif (sign > 0 and hi >= tp) or (sign < 0 and lo <= tp):
            self._execute_close(sym, "alvo")

    def run(self, cycles: int | None = None) -> None:
        k = 0
        log.info("Vorcaro iniciado | corretora=%s live=%s dry_run=%s universo=%s",
                 self.broker.name, self.broker.live, self.cfg.dry_run, self.cfg.universe)
        while cycles is None or k < cycles:
            t0 = time.monotonic()
            try:
                self.cycle()
            except Exception:  # um ciclo com erro não derruba o robô; fica registrado
                log.exception("erro no ciclo")
                self._journal("error")
            k += 1
            if cycles is not None and k >= cycles:
                break
            time.sleep(max(0.0, self.cfg.interval_s - (time.monotonic() - t0)))
