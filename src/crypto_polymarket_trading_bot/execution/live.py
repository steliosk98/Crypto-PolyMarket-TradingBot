from __future__ import annotations

from crypto_polymarket_trading_bot.strategy import StrategyDecision

from .base import ExecutionRecord, Position


class LiveExecutor:
    """Live execution placeholder."""

    @property
    def current_position(self) -> Position | None:
        return None

    def handle_decision(self, decision: StrategyDecision) -> list[ExecutionRecord]:
        raise NotImplementedError("Live execution is not implemented in the initial scaffold.")
