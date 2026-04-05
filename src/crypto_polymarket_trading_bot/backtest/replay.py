from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from crypto_polymarket_trading_bot.config import Settings
from crypto_polymarket_trading_bot.execution import PaperExecutor
from crypto_polymarket_trading_bot.strategy import OddsTick, SignalDirection, StrategyEngine

from .metrics import BacktestSummary


def load_ticks_from_csv(path: Path) -> list[OddsTick]:
    ticks: list[OddsTick] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            ticks.append(
                OddsTick(
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    up_odds=float(row["up_odds"]),
                    market_id=row.get("market_id") or None,
                )
            )
    return ticks


def run_backtest(ticks: list[OddsTick], settings: Settings) -> BacktestSummary:
    engine = StrategyEngine(settings)
    executor = PaperExecutor(settings)
    summary = BacktestSummary()

    for tick in ticks:
        summary.ticks_processed += 1
        decisions = engine.process_tick(tick)
        summary.decisions += len(decisions)
        for decision in decisions:
            records = executor.handle_decision(decision)
            if decision.target_position == SignalDirection.LONG:
                summary.entries += 1
                summary.long_entries += 1
            elif decision.target_position == SignalDirection.SHORT:
                summary.entries += 1
                summary.short_entries += 1
            elif decision.target_position == SignalDirection.FLAT:
                summary.exits += 1

            for record in records:
                if record.action == "CLOSE" and decision.target_position != SignalDirection.FLAT:
                    summary.exits += 1

    return summary
