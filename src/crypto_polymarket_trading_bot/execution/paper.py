from __future__ import annotations

from crypto_polymarket_trading_bot.config import Settings
from crypto_polymarket_trading_bot.strategy import SignalDirection, StrategyDecision

from .base import ExecutionRecord, Position


class PaperExecutor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._current_position: Position | None = None

    @property
    def current_position(self) -> Position | None:
        return self._current_position

    def handle_decision(self, decision: StrategyDecision) -> list[ExecutionRecord]:
        records: list[ExecutionRecord] = []

        if decision.target_position == SignalDirection.FLAT:
            if self._current_position is not None:
                records.append(self._close_position(decision))
            return records

        if self._current_position is not None and self._current_position.side == decision.target_position:
            return records

        if self._current_position is not None:
            records.append(self._close_position(decision))

        records.append(self._open_position(decision))
        return records

    def _open_position(self, decision: StrategyDecision) -> ExecutionRecord:
        self._current_position = Position(
            side=decision.target_position,
            opened_at=decision.timestamp,
            fixed_notional_usd=self.settings.fixed_notional_usd,
            fixed_margin_usd=self.settings.fixed_margin_usd,
            leverage=self.settings.leverage,
            market_id=decision.market_id,
        )
        return ExecutionRecord(
            timestamp=decision.timestamp,
            action="OPEN",
            side=decision.target_position,
            status="FILLED",
            fixed_notional_usd=self.settings.fixed_notional_usd,
            fixed_margin_usd=self.settings.fixed_margin_usd,
            leverage=self.settings.leverage,
            market_id=decision.market_id,
            details=decision.reason,
        )

    def _close_position(self, decision: StrategyDecision) -> ExecutionRecord:
        current_position = self._current_position
        if current_position is None:
            raise RuntimeError("Cannot close a position when no paper position is open.")

        self._current_position = None
        return ExecutionRecord(
            timestamp=decision.timestamp,
            action="CLOSE",
            side=current_position.side,
            status="FILLED",
            fixed_notional_usd=current_position.fixed_notional_usd,
            fixed_margin_usd=current_position.fixed_margin_usd,
            leverage=current_position.leverage,
            market_id=current_position.market_id,
            details=decision.reason,
        )
