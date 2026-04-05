from pathlib import Path

from crypto_polymarket_trading_bot.config.settings import AppMode, Settings


def test_settings_defaults() -> None:
    settings = Settings()
    assert settings.app_mode == AppMode.PAPER
    assert settings.db_path == Path("data/trading_bot.db")
    assert settings.up_threshold == 0.80
    assert settings.confirmation_seconds == 20
    assert settings.entry_cutoff_seconds == 150
    assert settings.backtest_fee_bps == 4.0


def test_settings_env_override(monkeypatch) -> None:
    monkeypatch.setenv("BOT_APP_MODE", "backtest")
    monkeypatch.setenv("BOT_DB_PATH", "data/test.db")
    settings = Settings()
    assert settings.app_mode == AppMode.BACKTEST
    assert settings.db_path == Path("data/test.db")
