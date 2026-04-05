from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from crypto_polymarket_trading_bot.strategy import SignalDirection, StrategyDecision


@dataclass(slots=True)
class Position:
    side: SignalDirection
    opened_at: datetime
    fixed_notional_usd: float
    fixed_margin_usd: float
    leverage: int
    market_id: str | None = None


@dataclass(slots=True)
class ExecutionRecord:
    timestamp: datetime
    action: str
    side: SignalDirection
    status: str
    fixed_notional_usd: float
    fixed_margin_usd: float
    leverage: int
    market_id: str | None = None
    details: str = ""


class Executor(Protocol):
    def handle_decision(self, decision: StrategyDecision) -> list[ExecutionRecord]:
        ...

    @property
    def current_position(self) -> Position | None:
        ...
