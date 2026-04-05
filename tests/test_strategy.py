from datetime import UTC, datetime, timedelta

from crypto_polymarket_trading_bot.config import Settings
from crypto_polymarket_trading_bot.strategy import OddsTick, SignalDirection, StrategyEngine


def make_tick(second_offset: int, up_odds: float) -> OddsTick:
    base = datetime(2026, 4, 5, 10, 0, 0, tzinfo=UTC)
    return OddsTick(timestamp=base + timedelta(seconds=second_offset), up_odds=up_odds, market_id="m1")


def test_long_requires_10_seconds_of_confirmation() -> None:
    engine = StrategyEngine(Settings())
    assert engine.process_tick(make_tick(0, 0.72)) == []
    assert engine.process_tick(make_tick(9, 0.74)) == []

    decisions = engine.process_tick(make_tick(10, 0.75))
    assert len(decisions) == 1
    assert decisions[0].target_position == SignalDirection.LONG
    assert decisions[0].reason == "threshold_confirmed"


def test_no_duplicate_entry_decisions_in_same_candle() -> None:
    engine = StrategyEngine(Settings())
    engine.process_tick(make_tick(0, 0.72))
    engine.process_tick(make_tick(10, 0.75))

    later_decisions = engine.process_tick(make_tick(20, 0.80))
    assert later_decisions == []


def test_candle_close_emits_flat_and_next_candle_can_emit_new_signal() -> None:
    engine = StrategyEngine(Settings())
    engine.process_tick(make_tick(0, 0.72))
    first = engine.process_tick(make_tick(10, 0.75))
    assert first[0].target_position == SignalDirection.LONG

    rollover_decisions = engine.process_tick(make_tick(300, 0.20))
    assert len(rollover_decisions) == 1
    assert rollover_decisions[0].target_position == SignalDirection.FLAT
    assert rollover_decisions[0].reason == "candle_close"

    assert engine.process_tick(make_tick(309, 0.20)) == []
    next_entry = engine.process_tick(make_tick(310, 0.20))
    assert len(next_entry) == 1
    assert next_entry[0].target_position == SignalDirection.SHORT


def test_neutral_ticks_do_not_emit_decisions() -> None:
    engine = StrategyEngine(Settings())
    decisions = engine.process_tick(make_tick(0, 0.50))
    assert decisions == []
