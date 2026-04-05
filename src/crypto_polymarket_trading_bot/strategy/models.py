from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class SignalDirection(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


@dataclass(slots=True)
class OddsTick:
    timestamp: datetime
    up_odds: float
    market_id: str | None = None


@dataclass(slots=True)
class StrategyDecision:
    target_position: SignalDirection
    reason: str
    timestamp: datetime
    candle_start: datetime
    candle_end: datetime
    up_odds: float
    market_id: str | None = None
    confirmation_progress_seconds: float = 0.0
