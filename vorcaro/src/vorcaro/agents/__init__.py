from .base import Agent
from .council import Council, Decision
from .scanner import Opportunity, ScannerAgent
from .signals import (
    AutocorrelationAgent,
    BinaryPatternAgent,
    MeanReversionAgent,
    MomentumAgent,
    OmegaAgent,
    SentimentAgent,
)

__all__ = ["Agent", "AutocorrelationAgent", "BinaryPatternAgent", "Council", "Decision", "MeanReversionAgent",
           "MomentumAgent", "OmegaAgent", "Opportunity", "ScannerAgent", "SentimentAgent"]


def default_agents() -> list[Agent]:
    patterns = BinaryPatternAgent()
    return [MomentumAgent(), MeanReversionAgent(), AutocorrelationAgent(), patterns,
            OmegaAgent(pattern_agent=patterns)]
