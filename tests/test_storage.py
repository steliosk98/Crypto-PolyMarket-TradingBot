from datetime import UTC, datetime
from pathlib import Path

from crypto_polymarket_trading_bot.execution import ExecutionRecord, Position
from crypto_polymarket_trading_bot.storage import Repository, initialize_database
from crypto_polymarket_trading_bot.strategy import OddsTick, SignalDirection, StrategyDecision


def test_database_initialization_and_basic_writes(tmp_path: Path) -> None:
    db_path = tmp_path / "bot.db"
    initialize_database(db_path)
    repository = Repository(db_path)

    tick = OddsTick(timestamp=datetime(2026, 4, 5, 10, 0, tzinfo=UTC), up_odds=0.73, market_id="m1")
    decision = StrategyDecision(
        target_position=SignalDirection.LONG,
        reason="threshold_confirmed",
        timestamp=tick.timestamp,
        candle_start=tick.timestamp,
        candle_end=tick.timestamp,
        up_odds=tick.up_odds,
        market_id=tick.market_id,
        confirmation_progress_seconds=10.0,
    )
    execution = ExecutionRecord(
        timestamp=tick.timestamp,
        action="OPEN",
        side=SignalDirection.LONG,
        status="FILLED",
        fixed_notional_usd=100.0,
        fixed_margin_usd=25.0,
        leverage=4,
        market_id="m1",
        details="threshold_confirmed",
    )
    position = Position(
        side=SignalDirection.LONG,
        opened_at=tick.timestamp,
        fixed_notional_usd=100.0,
        fixed_margin_usd=25.0,
        leverage=4,
        market_id="m1",
    )

    repository.log_signal_event(tick, tick.timestamp, SignalDirection.LONG, 10.0)
    repository.log_decision(decision)
    repository.log_execution(execution)
    repository.log_position_snapshot(position, tick.timestamp)

    counts = repository.counts()
    assert counts["signal_events"] == 1
    assert counts["decisions"] == 1
    assert counts["positions"] == 1
    assert counts["executions"] == 1
    assert repository.latest_decision() is not None
    assert repository.current_position() is not None
