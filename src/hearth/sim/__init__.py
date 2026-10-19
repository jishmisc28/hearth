"""Simulator package for offline token and prompt cache estimation."""

from hearth.sim.cache_sim import CacheSimulator, SimulatedCallResult, compute_calibration_mae
from hearth.sim.tokens import count_message_tokens, count_text_tokens, count_tool_tokens

__all__ = [
    "CacheSimulator",
    "SimulatedCallResult",
    "compute_calibration_mae",
    "count_text_tokens",
    "count_message_tokens",
    "count_tool_tokens",
]
