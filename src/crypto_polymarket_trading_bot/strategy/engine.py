from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from crypto_polymarket_trading_bot.config import Settings

from .models import OddsTick, SignalDirection, StrategyDecision


@dataclass(slots=True)
class CandidateState:
    direction: SignalDirection
    started_at: datetime


class StrategyEngine:
    """5m threshold-confirmation strategy."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._active_candle_start: datetime | None = None
        self._active_candle_end: datetime | None = None
        self._candidate: CandidateState | None = None
        self._entry_emitted: SignalDirection | None = None

    def process_tick(self, tick: OddsTick) -> list[StrategyDecision]:
        tick_time = self._normalize_ts(tick.timestamp)
        candle_start, candle_end = self._candle_bounds(tick_time)
        decisions: list[StrategyDecision] = []

        if self._active_candle_start is None:
            self._reset_candle(candle_start, candle_end)
        elif candle_start != self._active_candle_start:
            if self._entry_emitted is not None and self._active_candle_start is not None and self._active_candle_end is not None:
                decisions.append(
                    StrategyDecision(
                        target_position=SignalDirection.FLAT,
                        reason="candle_close",
                        timestamp=self._active_candle_end,
                        candle_start=self._active_candle_start,
                        candle_end=self._active_candle_end,
                        up_odds=tick.up_odds,
                        market_id=tick.market_id,
                    )
                )
            self._reset_candle(candle_start, candle_end)

        threshold_direction = self._threshold_direction(tick.up_odds)
        if threshold_direction is None or self._entry_emitted is not None:
            if threshold_direction is None:
                self._candidate = None
            return decisions

        if self._past_entry_cutoff(tick_time, candle_start):
            self._candidate = None
            return decisions

        if self._candidate is None or self._candidate.direction != threshold_direction:
            self._candidate = CandidateState(direction=threshold_direction, started_at=tick_time)
            return decisions

        progress = (tick_time - self._candidate.started_at).total_seconds()
        if progress >= self.settings.confirmation_seconds:
            self._entry_emitted = threshold_direction
            decisions.append(
                StrategyDecision(
                    target_position=threshold_direction,
                    reason="threshold_confirmed",
                    timestamp=tick_time,
                    candle_start=candle_start,
                    candle_end=candle_end,
                    up_odds=tick.up_odds,
                    market_id=tick.market_id,
                    confirmation_progress_seconds=progress,
                )
            )
        return decisions

    def confirmation_progress(self, tick: OddsTick) -> float:
        tick_time = self._normalize_ts(tick.timestamp)
        threshold_direction = self._threshold_direction(tick.up_odds)
        candle_start, _ = self._candle_bounds(tick_time)
        if self._past_entry_cutoff(tick_time, candle_start):
            return 0.0
        if threshold_direction is None or self._candidate is None:
            return 0.0
        if threshold_direction != self._candidate.direction:
            return 0.0
        return max(0.0, (tick_time - self._candidate.started_at).total_seconds())

    def classify_tick(self, tick: OddsTick) -> tuple[datetime, SignalDirection | None, float]:
        candle_start, _ = self._candle_bounds(tick.timestamp)
        direction = None if self._past_entry_cutoff(self._normalize_ts(tick.timestamp), candle_start) else self._threshold_direction(tick.up_odds)
        return candle_start, direction, self.confirmation_progress(tick)

    def _reset_candle(self, candle_start: datetime, candle_end: datetime) -> None:
        self._active_candle_start = candle_start
        self._active_candle_end = candle_end
        self._candidate = None
        self._entry_emitted = None

    def _threshold_direction(self, up_odds: float) -> SignalDirection | None:
        if up_odds >= self.settings.up_threshold:
            return SignalDirection.LONG
        if up_odds <= self.settings.down_threshold:
            return SignalDirection.SHORT
        return None

    def _past_entry_cutoff(self, timestamp: datetime, candle_start: datetime) -> bool:
        return (timestamp - candle_start).total_seconds() > self.settings.entry_cutoff_seconds

    def _candle_bounds(self, timestamp: datetime) -> tuple[datetime, datetime]:
        ts = self._normalize_ts(timestamp)
        minute_bucket = (ts.minute // self.settings.candle_minutes) * self.settings.candle_minutes
        candle_start = ts.replace(minute=minute_bucket, second=0, microsecond=0)
        candle_end = candle_start + timedelta(minutes=self.settings.candle_minutes)
        return candle_start, candle_end

    @staticmethod
    def _normalize_ts(timestamp: datetime) -> datetime:
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC)
