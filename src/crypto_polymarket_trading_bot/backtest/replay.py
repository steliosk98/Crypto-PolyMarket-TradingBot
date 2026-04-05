from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from crypto_polymarket_trading_bot.config import Settings
from crypto_polymarket_trading_bot.strategy import OddsTick, SignalDirection, StrategyDecision, StrategyEngine

from .metrics import BacktestSummary, CompletedTrade


@dataclass(slots=True)
class OpenTrade:
    side: SignalDirection
    entry_time: datetime
    entry_price: float
    fixed_notional_usd: float
    market_id: str | None = None


def load_ticks_from_csv(path: Path) -> list[OddsTick]:
    ticks: list[OddsTick] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            reference_price_raw = row.get("reference_price") or row.get("btc_price") or ""
            ticks.append(
                OddsTick(
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    up_odds=float(row["up_odds"]),
                    market_id=row.get("market_id") or None,
                    reference_price=float(reference_price_raw) if reference_price_raw else None,
                )
            )
    return ticks


def run_backtest(ticks: list[OddsTick], settings: Settings) -> BacktestSummary:
    engine = StrategyEngine(settings)
    summary = BacktestSummary()
    open_trade: OpenTrade | None = None
    cumulative_equity = 0.0
    peak_equity = 0.0

    for tick in ticks:
        summary.ticks_processed += 1
        decisions = engine.process_tick(tick)
        summary.decisions += len(decisions)

        for decision in decisions:
            if decision.target_position == SignalDirection.LONG:
                summary.entries += 1
                summary.long_entries += 1
                open_trade = _open_trade_from_decision(decision, tick, settings)
            elif decision.target_position == SignalDirection.SHORT:
                summary.entries += 1
                summary.short_entries += 1
                open_trade = _open_trade_from_decision(decision, tick, settings)
            elif decision.target_position == SignalDirection.FLAT:
                summary.exits += 1
                if open_trade is not None:
                    completed = _close_trade(open_trade, tick, settings)
                    summary.completed_trades += 1
                    summary.gross_pnl_usd += completed.gross_pnl_usd
                    summary.fees_usd += completed.fees_usd
                    summary.net_pnl_usd += completed.net_pnl_usd
                    summary.trades.append(completed)
                    if completed.net_pnl_usd >= 0:
                        summary.winning_trades += 1
                    else:
                        summary.losing_trades += 1
                    cumulative_equity += completed.net_pnl_usd
                    peak_equity = max(peak_equity, cumulative_equity)
                    summary.max_drawdown_usd = max(
                        summary.max_drawdown_usd,
                        peak_equity - cumulative_equity,
                    )
                    summary.equity_curve.append(cumulative_equity)
                    open_trade = None

    summary.finalize()
    return summary


def _open_trade_from_decision(
    decision: StrategyDecision,
    tick: OddsTick,
    settings: Settings,
) -> OpenTrade:
    entry_price = _price_from_tick(tick)
    return OpenTrade(
        side=decision.target_position,
        entry_time=decision.timestamp,
        entry_price=_apply_slippage(entry_price, decision.target_position, settings.backtest_slippage_bps, is_entry=True),
        fixed_notional_usd=settings.fixed_notional_usd,
        market_id=decision.market_id,
    )


def _close_trade(open_trade: OpenTrade, tick: OddsTick, settings: Settings) -> CompletedTrade:
    raw_exit_price = _price_from_tick(tick)
    exit_price = _apply_slippage(raw_exit_price, open_trade.side, settings.backtest_slippage_bps, is_entry=False)
    quantity = open_trade.fixed_notional_usd / open_trade.entry_price

    if open_trade.side == SignalDirection.LONG:
        gross_pnl = quantity * (exit_price - open_trade.entry_price)
    else:
        gross_pnl = quantity * (open_trade.entry_price - exit_price)

    fee_rate = settings.backtest_fee_bps / 10_000
    fees = (open_trade.fixed_notional_usd * fee_rate) * 2
    net_pnl = gross_pnl - fees

    return CompletedTrade(
        side=open_trade.side,
        entry_time=open_trade.entry_time,
        exit_time=tick.timestamp,
        entry_price=open_trade.entry_price,
        exit_price=exit_price,
        fixed_notional_usd=open_trade.fixed_notional_usd,
        gross_pnl_usd=gross_pnl,
        fees_usd=fees,
        net_pnl_usd=net_pnl,
        market_id=open_trade.market_id,
    )


def _price_from_tick(tick: OddsTick) -> float:
    if tick.reference_price is None:
        raise ValueError(
            "Backtest ticks must include 'reference_price' (or 'btc_price') to calculate trade PnL."
        )
    return tick.reference_price


def _apply_slippage(price: float, side: SignalDirection, slippage_bps: float, *, is_entry: bool) -> float:
    slippage_rate = slippage_bps / 10_000
    if slippage_rate == 0:
        return price

    if side == SignalDirection.LONG:
        return price * (1 + slippage_rate) if is_entry else price * (1 - slippage_rate)

    return price * (1 - slippage_rate) if is_entry else price * (1 + slippage_rate)
