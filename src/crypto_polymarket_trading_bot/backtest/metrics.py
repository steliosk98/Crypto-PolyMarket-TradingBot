from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from crypto_polymarket_trading_bot.strategy import SignalDirection


@dataclass(slots=True)
class CompletedTrade:
    side: SignalDirection
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    fixed_notional_usd: float
    gross_pnl_usd: float
    fees_usd: float
    net_pnl_usd: float
    market_id: str | None = None


@dataclass(slots=True)
class BacktestSummary:
    ticks_processed: int = 0
    decisions: int = 0
    entries: int = 0
    exits: int = 0
    long_entries: int = 0
    short_entries: int = 0
    completed_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    gross_pnl_usd: float = 0.0
    fees_usd: float = 0.0
    net_pnl_usd: float = 0.0
    avg_trade_net_pnl_usd: float = 0.0
    win_rate: float = 0.0
    max_drawdown_usd: float = 0.0
    equity_curve: list[float] = field(default_factory=list)
    trades: list[CompletedTrade] = field(default_factory=list)

    def finalize(self) -> None:
        if self.completed_trades > 0:
            self.avg_trade_net_pnl_usd = self.net_pnl_usd / self.completed_trades
            self.win_rate = self.winning_trades / self.completed_trades
