from vorcaro.agents import Council, default_agents
from vorcaro.agents.base import Agent
from vorcaro.backtest import BacktestConfig, run_backtest

CFG = BacktestConfig(warmup=300, fee_bps=0.5, slippage_bps=0.2)


class Spy(Agent):
    name = "spy"

    def __init__(self):
        self.seen = []

    def analyze(self, s):
        self.seen.append((len(s), s.ts[-1]))
        return None


def test_no_lookahead(rw):
    spy = Spy()
    run_backtest(rw, Council([spy]), CFG)
    # na barra i o agente vê exatamente as barras 0..i (com lookback >= len)
    for k, (n, ts) in enumerate(spy.seen):
        i = CFG.warmup + k
        assert n == i + 1 and ts == rw.ts[i]


def test_finds_edge_where_it_exists(reverting):
    r = run_backtest(reverting, Council(default_agents()), CFG)
    assert r.metrics.psr > 0.9 and r.metrics.total_return > 0


def test_flat_at_end_of_day_and_deterministic(reverting):
    a = run_backtest(reverting, Council(default_agents()), CFG)
    b = run_backtest(reverting, Council(default_agents()), CFG)
    assert a.metrics == b.metrics
    for t in a.trades:
        assert reverting.ts[t.exit_i].date() == reverting.ts[t.entry_i].date()
