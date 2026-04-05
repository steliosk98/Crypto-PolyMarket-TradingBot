from datetime import UTC, datetime, timedelta
from pathlib import Path

from crypto_polymarket_trading_bot.cli.main import main
from crypto_polymarket_trading_bot.data import BinanceKline, PolymarketPricePoint
from crypto_polymarket_trading_bot.historical import last_full_month_windows
from crypto_polymarket_trading_bot.storage import Repository


def test_db_init_command(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "cli.db"
    exit_code = main(["db-init", "--db-path", str(db_path)])
    output = capsys.readouterr().out
    assert exit_code == 0
    assert db_path.exists()
    assert "Initialized database" in output


def test_backtest_command(tmp_path: Path, capsys) -> None:
    csv_path = tmp_path / "ticks.csv"
    csv_path.write_text(
        "timestamp,up_odds,reference_price,market_id\n"
        "2026-04-05T10:00:00+00:00,0.82,84000,m1\n"
        "2026-04-05T10:00:20+00:00,0.84,84040,m1\n"
        "2026-04-05T10:05:00+00:00,0.18,84120,m2\n",
        encoding="utf-8",
    )
    exit_code = main(["backtest", "--input", str(csv_path)])
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Backtest summary" in output
    assert "completed_trades=1" in output


def test_build_historical_dataset_and_backtest_monthly(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "hist.db"
    repository = Repository(db_path)
    window = last_full_month_windows(1)[0]
    repository.insert_polymarket_history(
        [
            PolymarketPricePoint("m1", "slug-1", "tok1", window.start, 0.82),
            PolymarketPricePoint("m1", "slug-1", "tok1", window.start + timedelta(seconds=20), 0.84),
            PolymarketPricePoint("m1", "slug-1", "tok1", window.start + timedelta(minutes=5), 0.18),
        ]
    )
    repository.insert_binance_klines(
        [
            BinanceKline("BTCUSDT", "1m", window.start + timedelta(minutes=i), window.start + timedelta(minutes=i, seconds=59), 84000 + i * 5, 0, 0, 0, 1)
            for i in range(10)
        ]
    )

    build_exit = main(["build-historical-dataset", "--months", "1", "--db-path", str(db_path)])
    build_output = capsys.readouterr().out
    assert build_exit == 0
    assert "Built historical dataset ticks=" in build_output

    backtest_exit = main(["backtest-monthly", "--months", "1", "--db-path", str(db_path)])
    backtest_output = capsys.readouterr().out
    assert backtest_exit == 0
    assert "Monthly backtest summary" in backtest_output
    assert "Aggregate summary" in backtest_output
    assert repository.latest_monthly_summaries()
