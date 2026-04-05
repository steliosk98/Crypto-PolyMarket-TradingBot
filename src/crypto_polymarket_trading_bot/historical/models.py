from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from crypto_polymarket_trading_bot.strategy import SignalDirection


@dataclass(slots=True)
class HistoricalTick:
    timestamp: datetime
    month_key: str
    market_id: str
    market_slug: str | None
    up_odds_midpoint: float | None
    best_bid_yes: float | None
    best_ask_yes: float | None
    last_trade_yes: float | None
    reference_price: float | None


@dataclass(slots=True)
class SkippedTrade:
    month_key: str
    timestamp: datetime
    market_id: str | None
    side: SignalDirection
    reason: str
    details: str = ""


@dataclass(slots=True)
class HistoricalTrade:
    month_key: str
    side: SignalDirection
    market_id: str | None
    market_slug: str | None
    entry_time: datetime
    planned_exit_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    fixed_notional_usd: float
    gross_pnl_usd: float
    fees_usd: float
    net_pnl_usd: float


@dataclass(slots=True)
class MonthlyBacktestSummary:
    month_key: str
    signal_points_total: int = 0
    signal_points_usable: int = 0
    binance_points: int = 0
    decisions: int = 0
    trades_attempted: int = 0
    trades_executed: int = 0
    skipped_trades: int = 0
    long_trades: int = 0
    short_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    gross_pnl_usd: float = 0.0
    fees_usd: float = 0.0
    net_pnl_usd: float = 0.0
    avg_trade_net_pnl_usd: float = 0.0
    win_rate: float = 0.0
    max_drawdown_usd: float = 0.0
    equity_curve: list[float] = field(default_factory=list)

    def finalize(self) -> None:
        if self.trades_executed > 0:
            self.avg_trade_net_pnl_usd = self.net_pnl_usd / self.trades_executed
            self.win_rate = self.winning_trades / self.trades_executed


@dataclass(slots=True)
class AggregateBacktestSummary:
    months: int = 0
    trades_attempted: int = 0
    trades_executed: int = 0
    skipped_trades: int = 0
    long_trades: int = 0
    short_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    gross_pnl_usd: float = 0.0
    fees_usd: float = 0.0
    net_pnl_usd: float = 0.0
    avg_trade_net_pnl_usd: float = 0.0
    win_rate: float = 0.0
    max_drawdown_usd: float = 0.0

    def finalize(self) -> None:
        if self.trades_executed > 0:
            self.avg_trade_net_pnl_usd = self.net_pnl_usd / self.trades_executed
            self.win_rate = self.winning_trades / self.trades_executed


@dataclass(slots=True)
class MonthlyBacktestReport:
    monthly_summaries: list[MonthlyBacktestSummary]
    aggregate_summary: AggregateBacktestSummary
    trades: list[HistoricalTrade]
    skipped_trades: list[SkippedTrade]
