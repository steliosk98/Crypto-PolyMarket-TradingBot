from pathlib import Path

from crypto_polymarket_trading_bot.cli.main import main


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
        "timestamp,up_odds,market_id\n"
        "2026-04-05T10:00:00+00:00,0.72,m1\n"
        "2026-04-05T10:00:10+00:00,0.74,m1\n",
        encoding="utf-8",
    )
    exit_code = main(["backtest", "--input", str(csv_path)])
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Backtest summary" in output
