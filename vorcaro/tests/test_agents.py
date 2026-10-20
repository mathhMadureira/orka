from vorcaro.agents import AutocorrelationAgent, BinaryPatternAgent, Council
from vorcaro.agents.base import Agent
from vorcaro.core.models import Signal


class Fixed(Agent):
    def __init__(self, name, d):
        self.name, self.d = name, d

    def analyze(self, s):
        return Signal(self.name, s.symbol, self.d, 1.0)


def test_hedge_upweights_the_agent_that_is_right(rw):
    c = Council([Fixed("bull", 1.0), Fixed("bear", -1.0)], eta=0.3)
    for _ in range(30):
        c.decide(rw)
        c.learn(rw.symbol, +0.01)
    assert c.weight(rw.symbol, "bull") > 5 * c.weight(rw.symbol, "bear")
    assert c.decide(rw).score > 0.5


def test_statistical_agents_abstain_on_random_walk(rw):
    assert AutocorrelationAgent().analyze(rw) is None
    assert BinaryPatternAgent().analyze(rw) is None


def test_autocorr_detects_reversion(reverting):
    sig = AutocorrelationAgent().analyze(reverting)
    assert sig is not None and "ρ1=-" in sig.rationale
