from datetime import UTC, datetime, timedelta

from crypto_polymarket_trading_bot.backtest import run_backtest
from crypto_polymarket_trading_bot.config import Settings
from crypto_polymarket_trading_bot.strategy import OddsTick


BASE = datetime(2026, 4, 5, 10, 0, 0, tzinfo=UTC)


def make_tick(second_offset: int, up_odds: float, price: float, market_id: str) -> OddsTick:
    return OddsTick(
        timestamp=BASE + timedelta(seconds=second_offset),
        up_odds=up_odds,
        reference_price=price,
        market_id=market_id,
    )


def test_backtest_computes_completed_trade_metrics() -> None:
    settings = Settings()
    ticks = [
        make_tick(0, 0.82, 84000, "m1"),
        make_tick(20, 0.84, 84040, "m1"),
        make_tick(300, 0.18, 84120, "m2"),
    ]

    summary = run_backtest(ticks, settings)

    assert summary.entries == 1
    assert summary.exits == 1
    assert summary.completed_trades == 1
    assert summary.winning_trades == 1
    assert summary.losing_trades == 0
    assert summary.gross_pnl_usd > 0
    assert summary.fees_usd > 0
    assert summary.net_pnl_usd > 0
    assert len(summary.trades) == 1


def test_backtest_requires_reference_price() -> None:
    settings = Settings()
    ticks = [
        OddsTick(timestamp=BASE, up_odds=0.82, market_id="m1", reference_price=None),
        OddsTick(timestamp=BASE + timedelta(seconds=20), up_odds=0.84, market_id="m1", reference_price=None),
    ]

    try:
        run_backtest(ticks, settings)
    except ValueError as exc:
        assert "reference_price" in str(exc)
    else:
        raise AssertionError("Expected backtest to require reference_price for trade simulation")
