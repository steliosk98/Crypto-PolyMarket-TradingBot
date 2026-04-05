from pathlib import Path

from crypto_polymarket_trading_bot.config.settings import AppMode, Settings


def test_settings_defaults() -> None:
    settings = Settings()
    assert settings.app_mode == AppMode.PAPER
    assert settings.db_path == Path("data/trading_bot.db")
    assert settings.up_threshold == 0.80
    assert settings.confirmation_seconds == 20
    assert settings.down_threshold == 0.80
    assert settings.entry_cutoff_seconds == 900
    assert settings.five_minute_up_threshold == 0.90
    assert settings.five_minute_down_threshold == 0.90
    assert settings.five_minute_confirmation_seconds == 30
    assert settings.five_minute_entry_cutoff_seconds == 60
    assert settings.one_hour_up_threshold == 0.75
    assert settings.one_hour_down_threshold == 0.75
    assert settings.one_hour_confirmation_seconds == 120
    assert settings.one_hour_entry_cutoff_seconds == 900
    assert settings.backtest_fee_bps == 4.0


def test_settings_env_override(monkeypatch) -> None:
    monkeypatch.setenv("BOT_APP_MODE", "backtest")
    monkeypatch.setenv("BOT_DB_PATH", "data/test.db")
    settings = Settings()
    assert settings.app_mode == AppMode.BACKTEST
    assert settings.db_path == Path("data/test.db")


def test_strategy_profiles() -> None:
    settings = Settings()
    five = settings.strategy_profile("5m")
    oneh = settings.strategy_profile("1h")

    assert five.name == "5m"
    assert five.candle_minutes == 5
    assert five.up_threshold == 0.90
    assert five.down_threshold == 0.90
    assert five.confirmation_seconds == 30
    assert five.entry_cutoff_seconds == 60

    assert oneh.name == "1h"
    assert oneh.candle_minutes == 60
    assert oneh.up_threshold == 0.75
    assert oneh.down_threshold == 0.75
    assert oneh.confirmation_seconds == 120
    assert oneh.entry_cutoff_seconds == 900
