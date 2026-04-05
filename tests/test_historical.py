from datetime import UTC, datetime, timedelta

from crypto_polymarket_trading_bot.config import Settings
from crypto_polymarket_trading_bot.data import BinanceKline, PolymarketMarket, PolymarketPricePoint
from crypto_polymarket_trading_bot.historical import build_historical_ticks, last_full_month_windows, run_monthly_backtests
from crypto_polymarket_trading_bot.ingestion.historical import _is_btc_5m_market


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
        build_tick(window.start, 0.82, 84000),
        build_tick(window.start + timedelta(seconds=20), 0.84, 84020),
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
        build_tick(window.start, 0.82, 84000),
        build_tick(window.start + timedelta(seconds=20), 0.84, 84020),
        build_tick(window.start + timedelta(minutes=5), 0.18, 84100),
        build_tick(window.start + timedelta(minutes=5, seconds=20), 0.16, 84060),
        build_tick(window.start + timedelta(minutes=10), 0.82, 83980),
        build_tick(window.start + timedelta(minutes=10, seconds=20), 0.84, 84010),
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


def test_btc_5m_market_filter_matches_current_slug_pattern() -> None:
    market = PolymarketMarket(
        id="1",
        slug="btc-updown-5m-1766101200",
        question="Bitcoin Up or Down - December 18, 6:40PM-6:45PM ET",
        active=True,
        closed=True,
        accepting_orders=False,
        best_bid=None,
        best_ask=None,
        last_trade_price=None,
        outcomes=["Up", "Down"],
        outcome_prices=[0.5, 0.5],
        clob_token_ids=["up", "down"],
    )

    assert _is_btc_5m_market(market) is True


def test_btc_5m_market_filter_rejects_15m_slug() -> None:
    market = PolymarketMarket(
        id="2",
        slug="btc-updown-15m-1766101200",
        question="Bitcoin Up or Down - December 18, 6:30PM-6:45PM ET",
        active=True,
        closed=True,
        accepting_orders=False,
        best_bid=None,
        best_ask=None,
        last_trade_price=None,
        outcomes=["Up", "Down"],
        outcome_prices=[0.5, 0.5],
        clob_token_ids=["up", "down"],
    )

    assert _is_btc_5m_market(market) is False
