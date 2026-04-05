from datetime import UTC, datetime, timedelta

from crypto_polymarket_trading_bot.config import Settings
from crypto_polymarket_trading_bot.data import BinanceKline, PolymarketPricePoint
from crypto_polymarket_trading_bot.historical import build_historical_ticks, last_full_month_windows, run_monthly_backtests


def test_last_full_month_windows_utc() -> None:
    windows = last_full_month_windows(2, now=datetime(2026, 4, 5, 12, 0, tzinfo=UTC))
    assert [row.month_key for row in windows] == ["2026-02", "2026-03"]
    assert windows[0].start == datetime(2026, 2, 1, 0, 0, tzinfo=UTC)
    assert windows[1].end == datetime(2026, 4, 1, 0, 0, tzinfo=UTC)


def test_build_historical_ticks_joins_binance_reference_price() -> None:
    points = [
        PolymarketPricePoint("m1", "slug-1", "tok1", datetime(2026, 3, 1, 0, 0, tzinfo=UTC), 0.72),
        PolymarketPricePoint("m1", "slug-1", "tok1", datetime(2026, 3, 1, 0, 1, tzinfo=UTC), 0.74),
    ]
    klines = [
        BinanceKline("BTCUSDT", "1m", datetime(2026, 3, 1, 0, 0, tzinfo=UTC), datetime(2026, 3, 1, 0, 0, 59, tzinfo=UTC), 84000, 84100, 83950, 84050, 1),
        BinanceKline("BTCUSDT", "1m", datetime(2026, 3, 1, 0, 1, tzinfo=UTC), datetime(2026, 3, 1, 0, 1, 59, tzinfo=UTC), 84060, 84120, 84020, 84100, 1),
    ]
    ticks = build_historical_ticks(points, klines)
    assert len(ticks) == 2
    assert ticks[0].reference_price == 84000
    assert ticks[1].reference_price == 84060


def test_monthly_backtest_skips_missing_exit_price() -> None:
    settings = Settings()
    window = last_full_month_windows(1, now=datetime(2026, 4, 5, 12, 0, tzinfo=UTC))[0]
    ticks = [
        build_tick(window.start, 0.72, 84000),
        build_tick(window.start + timedelta(seconds=10), 0.74, 84020),
    ]
    klines = [
        BinanceKline("BTCUSDT", "1m", window.start, window.start + timedelta(seconds=59), 84000, 84020, 83980, 84010, 1),
    ]
    report = run_monthly_backtests(ticks, klines, settings, [window])
    summary = report.monthly_summaries[0]
    assert summary.trades_attempted == 1
    assert summary.trades_executed == 0
    assert summary.skipped_trades == 1
    assert report.skipped_trades[0].reason == "exit_price_missing"


def test_monthly_backtest_rollup() -> None:
    settings = Settings()
    window = last_full_month_windows(1, now=datetime(2026, 4, 5, 12, 0, tzinfo=UTC))[0]
    ticks = [
        build_tick(window.start, 0.72, 84000),
        build_tick(window.start + timedelta(seconds=10), 0.74, 84020),
        build_tick(window.start + timedelta(minutes=5), 0.20, 84100),
        build_tick(window.start + timedelta(minutes=5, seconds=10), 0.18, 84060),
        build_tick(window.start + timedelta(minutes=10), 0.80, 83980),
    ]
    klines = [
        BinanceKline("BTCUSDT", "1m", window.start + timedelta(minutes=i), window.start + timedelta(minutes=i, seconds=59), 84000 + i * 10, 0, 0, 0, 1)
        for i in range(16)
    ]
    report = run_monthly_backtests(ticks, klines, settings, [window])
    assert report.aggregate_summary.trades_attempted >= 2
    assert report.aggregate_summary.trades_executed >= 2
    assert len(report.trades) == report.aggregate_summary.trades_executed


def build_tick(timestamp: datetime, up_odds: float, reference_price: float):
    from crypto_polymarket_trading_bot.historical import HistoricalTick

    return HistoricalTick(
        timestamp=timestamp,
        month_key=timestamp.strftime("%Y-%m"),
        market_id="m1",
        market_slug="slug-1",
        up_odds_midpoint=up_odds,
        best_bid_yes=None,
        best_ask_yes=None,
        last_trade_yes=up_odds,
        reference_price=reference_price,
    )
