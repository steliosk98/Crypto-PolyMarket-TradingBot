from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from crypto_polymarket_trading_bot.config import Settings
from crypto_polymarket_trading_bot.data import BinanceKline, PolymarketPricePoint
from crypto_polymarket_trading_bot.strategy import OddsTick, SignalDirection, StrategyEngine

from .models import (
    AggregateBacktestSummary,
    HistoricalTick,
    HistoricalTrade,
    MonthlyBacktestReport,
    MonthlyBacktestSummary,
    SkippedTrade,
)


@dataclass(slots=True)
class MonthWindow:
    month_key: str
    start: datetime
    end: datetime


@dataclass(slots=True)
class OpenHistoricalTrade:
    month_key: str
    side: SignalDirection
    market_id: str | None
    market_slug: str | None
    entry_time: datetime
    planned_exit_time: datetime
    entry_price: float


def last_full_month_windows(months: int, now: datetime | None = None) -> list[MonthWindow]:
    current = (now or datetime.now(tz=UTC)).astimezone(UTC)
    first_of_current = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    windows: list[MonthWindow] = []

    cursor = first_of_current
    for _ in range(months):
        month_end = cursor
        month_start = (month_end - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        windows.append(MonthWindow(month_key=month_start.strftime("%Y-%m"), start=month_start, end=month_end))
        cursor = month_start

    windows.reverse()
    return windows


def build_historical_ticks(
    polymarket_points: list[PolymarketPricePoint],
    binance_klines: list[BinanceKline],
) -> list[HistoricalTick]:
    sorted_klines = sorted(binance_klines, key=lambda row: row.open_time)
    kline_times = [row.open_time for row in sorted_klines]
    ticks: list[HistoricalTick] = []

    for point in sorted(polymarket_points, key=lambda row: row.timestamp):
        index = bisect_left(kline_times, point.timestamp)
        reference_price = sorted_klines[index].open_price if index < len(sorted_klines) else None
        ticks.append(
            HistoricalTick(
                timestamp=point.timestamp,
                month_key=point.timestamp.strftime("%Y-%m"),
                market_id=point.market_id,
                market_slug=point.market_slug,
                up_odds_midpoint=point.price,
                best_bid_yes=None,
                best_ask_yes=None,
                last_trade_yes=point.price,
                reference_price=reference_price,
            )
        )
    return ticks


def run_monthly_backtests(
    historical_ticks: list[HistoricalTick],
    binance_klines: list[BinanceKline],
    settings: Settings,
    month_windows: list[MonthWindow],
) -> MonthlyBacktestReport:
    sorted_ticks = sorted(historical_ticks, key=lambda row: row.timestamp)
    sorted_klines = sorted(binance_klines, key=lambda row: row.open_time)
    aggregate = AggregateBacktestSummary(months=len(month_windows))
    monthly_summaries: list[MonthlyBacktestSummary] = []
    all_trades: list[HistoricalTrade] = []
    skipped_trades: list[SkippedTrade] = []

    for window in month_windows:
        month_ticks = [row for row in sorted_ticks if window.start <= row.timestamp < window.end]
        month_klines = [row for row in sorted_klines if window.start <= row.open_time < window.end or row.open_time >= window.end]
        summary, trades, skipped = _run_single_month(window, month_ticks, month_klines, settings)
        monthly_summaries.append(summary)
        all_trades.extend(trades)
        skipped_trades.extend(skipped)
        _accumulate_aggregate(aggregate, summary)

    aggregate.finalize()
    return MonthlyBacktestReport(
        monthly_summaries=monthly_summaries,
        aggregate_summary=aggregate,
        trades=all_trades,
        skipped_trades=skipped_trades,
    )


def _run_single_month(
    window: MonthWindow,
    historical_ticks: list[HistoricalTick],
    binance_klines: list[BinanceKline],
    settings: Settings,
) -> tuple[MonthlyBacktestSummary, list[HistoricalTrade], list[SkippedTrade]]:
    engine = StrategyEngine(settings)
    summary = MonthlyBacktestSummary(month_key=window.month_key)
    trades: list[HistoricalTrade] = []
    skipped: list[SkippedTrade] = []
    open_trade: OpenHistoricalTrade | None = None
    cumulative_equity = 0.0

    summary.signal_points_total = len(historical_ticks)
    summary.signal_points_usable = sum(1 for row in historical_ticks if row.up_odds_midpoint is not None)
    summary.binance_points = sum(1 for row in binance_klines if window.start <= row.open_time < window.end)

    for tick in historical_ticks:
        if open_trade is not None and tick.timestamp >= open_trade.planned_exit_time:
            open_trade = _close_open_trade(open_trade, binance_klines, settings, trades, skipped, summary, cumulative_equity)
            cumulative_equity = summary.equity_curve[-1] if summary.equity_curve else cumulative_equity

        if tick.up_odds_midpoint is None:
            continue

        decisions = engine.process_tick(
            OddsTick(
                timestamp=tick.timestamp,
                up_odds=tick.up_odds_midpoint,
                market_id=tick.market_id,
                reference_price=tick.reference_price,
            )
        )
        summary.decisions += len(decisions)

        for decision in decisions:
            if decision.target_position == SignalDirection.FLAT:
                continue
            summary.trades_attempted += 1
            entry_price = _find_fill_price(binance_klines, decision.timestamp)
            if entry_price is None:
                summary.skipped_trades += 1
                skipped.append(
                    SkippedTrade(
                        month_key=window.month_key,
                        timestamp=decision.timestamp,
                        market_id=decision.market_id,
                        side=decision.target_position,
                        reason="entry_price_missing",
                    )
                )
                continue

            if decision.target_position == SignalDirection.LONG:
                summary.long_trades += 1
            else:
                summary.short_trades += 1

            open_trade = OpenHistoricalTrade(
                month_key=window.month_key,
                side=decision.target_position,
                market_id=decision.market_id,
                market_slug=tick.market_slug,
                entry_time=decision.timestamp,
                planned_exit_time=decision.candle_end,
                entry_price=_apply_slippage(entry_price, decision.target_position, settings.backtest_slippage_bps, is_entry=True),
            )

    if open_trade is not None:
        _close_open_trade(open_trade, binance_klines, settings, trades, skipped, summary, cumulative_equity)

    summary.finalize()
    return summary, trades, skipped


def _close_open_trade(
    open_trade: OpenHistoricalTrade,
    binance_klines: list[BinanceKline],
    settings: Settings,
    trades: list[HistoricalTrade],
    skipped: list[SkippedTrade],
    summary: MonthlyBacktestSummary,
    cumulative_equity: float,
) -> None:
    exit_price = _find_fill_price(binance_klines, open_trade.planned_exit_time)
    if exit_price is None:
        summary.skipped_trades += 1
        skipped.append(
            SkippedTrade(
                month_key=open_trade.month_key,
                timestamp=open_trade.planned_exit_time,
                market_id=open_trade.market_id,
                side=open_trade.side,
                reason="exit_price_missing",
            )
        )
        return None

    adjusted_exit_price = _apply_slippage(exit_price, open_trade.side, settings.backtest_slippage_bps, is_entry=False)
    quantity = settings.fixed_notional_usd / open_trade.entry_price
    if open_trade.side == SignalDirection.LONG:
        gross_pnl = quantity * (adjusted_exit_price - open_trade.entry_price)
    else:
        gross_pnl = quantity * (open_trade.entry_price - adjusted_exit_price)

    fees = (settings.fixed_notional_usd * (settings.backtest_fee_bps / 10_000)) * 2
    net_pnl = gross_pnl - fees
    trade = HistoricalTrade(
        month_key=open_trade.month_key,
        side=open_trade.side,
        market_id=open_trade.market_id,
        market_slug=open_trade.market_slug,
        entry_time=open_trade.entry_time,
        planned_exit_time=open_trade.planned_exit_time,
        exit_time=open_trade.planned_exit_time,
        entry_price=open_trade.entry_price,
        exit_price=adjusted_exit_price,
        fixed_notional_usd=settings.fixed_notional_usd,
        gross_pnl_usd=gross_pnl,
        fees_usd=fees,
        net_pnl_usd=net_pnl,
    )
    trades.append(trade)
    summary.trades_executed += 1
    summary.gross_pnl_usd += gross_pnl
    summary.fees_usd += fees
    summary.net_pnl_usd += net_pnl
    if net_pnl >= 0:
        summary.winning_trades += 1
    else:
        summary.losing_trades += 1

    new_equity = cumulative_equity + net_pnl
    peak_equity = max(summary.equity_curve) if summary.equity_curve else 0.0
    peak_equity = max(peak_equity, new_equity)
    summary.max_drawdown_usd = max(summary.max_drawdown_usd, peak_equity - new_equity)
    summary.equity_curve.append(new_equity)
    return None


def _find_fill_price(binance_klines: list[BinanceKline], timestamp: datetime) -> float | None:
    for row in binance_klines:
        if row.open_time <= timestamp <= row.close_time:
            return row.open_price
        if row.open_time >= timestamp:
            return row.open_price
    return None


def _apply_slippage(price: float, side: SignalDirection, slippage_bps: float, *, is_entry: bool) -> float:
    slippage_rate = slippage_bps / 10_000
    if slippage_rate == 0:
        return price
    if side == SignalDirection.LONG:
        return price * (1 + slippage_rate) if is_entry else price * (1 - slippage_rate)
    return price * (1 - slippage_rate) if is_entry else price * (1 + slippage_rate)


def _accumulate_aggregate(aggregate: AggregateBacktestSummary, summary: MonthlyBacktestSummary) -> None:
    aggregate.trades_attempted += summary.trades_attempted
    aggregate.trades_executed += summary.trades_executed
    aggregate.skipped_trades += summary.skipped_trades
    aggregate.long_trades += summary.long_trades
    aggregate.short_trades += summary.short_trades
    aggregate.winning_trades += summary.winning_trades
    aggregate.losing_trades += summary.losing_trades
    aggregate.gross_pnl_usd += summary.gross_pnl_usd
    aggregate.fees_usd += summary.fees_usd
    aggregate.net_pnl_usd += summary.net_pnl_usd
    aggregate.max_drawdown_usd = max(aggregate.max_drawdown_usd, summary.max_drawdown_usd)
