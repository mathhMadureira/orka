"""Linha de comando do Vorcaro.

Fontes de dados (--source):
    synthetic[:ar]           série sintética (ar>0 tendência, ar<0 reversão, 0 aleatória)
    csv:caminho.csv          arquivo local
    binance:BTCUSDT          klines públicos da Binance
    yahoo:PETR4.SA           Yahoo Finance (B3 com sufixo .SA, EUA sem sufixo)
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import time as dtime

from . import config as cfgmod
from .agents import Council, SentimentAgent, default_agents
from .backtest import run_backtest, walk_forward
from .brokers import BrokerError, make_broker
from .data import providers
from .data.series import Series
from .quant import indicators as ind
from .quant.binary import (
    BinaryEncoder,
    BinaryPatternMiner,
    conditional_entropy_rate,
    lempel_ziv_complexity,
)
from .quant.equation import omega
from .quant.stats import hurst_rs
from .risk import RiskManager


def load_source(src: str, interval: str, bars: int) -> Series:
    kind, _, arg = src.partition(":")
    if kind == "synthetic":
        return providers.synthetic(n=bars, ar=float(arg or 0.0))
    if kind == "csv":
        return providers.load_csv(arg)
    if kind == "binance":
        return providers.binance_klines(arg or "BTCUSDT", interval, bars)
    if kind == "yahoo":
        return providers.yahoo_chart(arg, interval, "60d" if interval != "1m" else "7d").tail(bars)
    raise SystemExit(f"fonte desconhecida: {src}")


def cmd_backtest(a: argparse.Namespace) -> None:
    risk, bt = cfgmod.load(a.config)
    s = load_source(a.source, a.interval, a.bars)
    print(f"{s.symbol}: {len(s)} barras de {s.ts[0]} a {s.ts[-1]}")
    if a.walk_forward:
        for k, r in enumerate(walk_forward(s, lambda: Council(default_agents()), a.walk_forward, bt), 1):
            print(f"  bloco {k}: {r.metrics.report()}")
        return
    r = run_backtest(s, Council(default_agents()), bt)
    print(r.metrics.report())
    print("pesos aprendidos:", {k: round(v, 3) for k, v in r.weights.items()})
    print("vetos de risco:", dict(sorted(r.vetoes.items(), key=lambda kv: -kv[1])[:6]))
    if a.trades:
        for t in r.trades[-a.trades:]:
            print(f"  {t.side.value:4} {t.qty} {t.entry}->{t.exit} pnl={t.pnl:+.2f} ({t.reason})")


def cmd_patterns(a: argparse.Namespace) -> None:
    s = load_source(a.source, a.interval, a.bars)
    r = ind.log_returns(s.close)
    split = int(len(r) * 0.7)
    enc = BinaryEncoder(a.ret_bits, not a.no_volume).fit(r[:split - 1])
    sym = enc.encode(r, s.volume[1:] if enc.vol_bit else None)
    miner = BinaryPatternMiner(max_len=a.max_len, min_support=a.min_support,
                               alpha=a.alpha).fit(sym[:split - 1], r[1:split])
    print(f"bits/símbolo={enc.bits_per_symbol} padrões testados={miner.tested} "
          f"significativos (FDR {a.alpha:.0%})={len(miner.patterns)} taxa base={miner.base_rate:.3f}")
    print(f"entropia condicional (ordem 3) = {conditional_entropy_rate(sym, 3, enc.alphabet):.4f}  "
          f"LZ76 (bits de direção) = {lempel_ziv_complexity((r > 0).astype(int)):.4f}")
    # validação fora da amostra: os padrões continuam valendo nos 30% finais?
    oos_hits = oos_right = 0
    for t in range(split, len(sym) - 1):
        hit = miner.match(sym[: t + 1])
        if hit is not None and r[t + 1] != 0:
            oos_hits += 1
            oos_right += (hit.edge > 0) == (r[t + 1] > 0)
    for p in miner.top(a.top):
        print(f"  [{p.bits(enc.bits_per_symbol)}] n={p.n:5d} p̂(alta)={p.p_post:.3f} "
              f"ret.médio={p.mean_ret:+.5f} q={p.q_value:.2e}")
    if oos_hits:
        print(f"fora da amostra: {oos_hits} sinais, acerto {oos_right / oos_hits:.1%}")
    else:
        print("fora da amostra: nenhum padrão disparou")


def cmd_omega(a: argparse.Namespace) -> None:
    s = load_source(a.source, a.interval, a.bars)
    r = omega(s.tail(400))
    print(r.explain() if r else "histórico insuficiente")
    print(f"Hurst (todo histórico) = {hurst_rs(ind.log_returns(s.close)):.3f}")


def cmd_news(a: argparse.Namespace) -> None:
    from .scraping.news import DEFAULT_FEEDS, fetch_feed, symbol_sentiment

    items = []
    for name, url in DEFAULT_FEEDS.items():
        try:
            items += fetch_feed(name, url.format(symbol=a.symbol))
        except Exception as e:  # noqa: BLE001 — feeds externos falham de muitas formas
            print(f"  feed {name} indisponível: {e}", file=sys.stderr)
    aliases = [a.symbol] + (a.aliases.split(",") if a.aliases else [])
    score, n = symbol_sentiment(items, aliases)
    print(f"{a.symbol}: sentimento {score:+.3f} em {n} notícias ({len(items)} lidas)")


def cmd_run(a: argparse.Namespace) -> None:
    from .engine.live import LiveConfig, LiveEngine

    risk_cfg, _ = cfgmod.load(a.config)
    try:
        broker = make_broker(a.broker, live_flag=a.live)
    except BrokerError as e:
        raise SystemExit(f"erro: {e}") from e
    if broker.live:
        print("ATENÇÃO: modo LIVE — ordens com dinheiro real.", file=sys.stderr)
    data_fn = None
    if a.data:
        data_fn = lambda sym: load_source(f"{a.data}:{sym}", a.interval, a.bars)  # noqa: E731
    agents = default_agents()
    if a.sentiment:
        agents.append(SentimentAgent())
    close = dtime.fromisoformat(a.session_close) if a.session_close else None
    eng = LiveEngine(broker, Council(agents), RiskManager(risk_cfg),
                     LiveConfig(a.universe.split(","), a.interval, a.bars, a.every, a.top,
                                close, dry_run=not a.execute), data_fn)
    eng.run(cycles=a.cycles)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser("vorcaro", description="Sistema multiagente de day trade")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    def src(sp):
        sp.add_argument("--source", default="synthetic")
        sp.add_argument("--interval", default="5m")
        sp.add_argument("--bars", type=int, default=3000)

    b = sub.add_parser("backtest", help="backtest sem look-ahead")
    src(b)
    b.add_argument("--config")
    b.add_argument("--walk-forward", type=int, default=0)
    b.add_argument("--trades", type=int, default=0, help="mostra os N últimos trades")
    b.set_defaults(fn=cmd_backtest)

    pt = sub.add_parser("patterns", help="minera padrões binários (com validação fora da amostra)")
    src(pt)
    pt.add_argument("--ret-bits", type=int, default=1)
    pt.add_argument("--no-volume", action="store_true")
    pt.add_argument("--max-len", type=int, default=6)
    pt.add_argument("--min-support", type=int, default=30)
    pt.add_argument("--alpha", type=float, default=0.05)
    pt.add_argument("--top", type=int, default=10)
    pt.set_defaults(fn=cmd_patterns)

    o = sub.add_parser("omega", help="leitura atual da Equação Vorcaro")
    src(o)
    o.set_defaults(fn=cmd_omega)

    nw = sub.add_parser("news", help="raspa notícias e calcula sentimento")
    nw.add_argument("--symbol", required=True)
    nw.add_argument("--aliases", default="")
    nw.set_defaults(fn=cmd_news)

    r = sub.add_parser("run", help="motor ao vivo (padrão: simulação, nenhuma ordem enviada)")
    r.add_argument("--broker", default="paper", choices=["paper", "ccxt", "alpaca", "mt5"])
    r.add_argument("--universe", required=True, help="ex.: BTC/USDT,ETH/USDT ou AAPL,MSFT")
    r.add_argument("--data", help="fonte de dados alternativa (binance|yahoo); padrão: a corretora")
    r.add_argument("--interval", default="5m")
    r.add_argument("--bars", type=int, default=1500)
    r.add_argument("--every", type=int, default=300, help="segundos entre ciclos")
    r.add_argument("--top", type=int, default=3)
    r.add_argument("--cycles", type=int)
    r.add_argument("--session-close", help="HH:MM UTC para zerar posições")
    r.add_argument("--sentiment", action="store_true")
    r.add_argument("--config")
    r.add_argument("--execute", action="store_true",
                   help="envia ordens (sandbox/paper/demo, a menos que --live)")
    r.add_argument("--live", action="store_true", help="dinheiro real; exige VORCARO_LIVE=1")
    r.set_defaults(fn=cmd_run)

    a = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    a.fn(a)


if __name__ == "__main__":
    main()
