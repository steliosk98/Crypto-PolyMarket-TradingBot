from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppMode(StrEnum):
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


@dataclass(frozen=True, slots=True)
class StrategyProfile:
    name: str
    candle_minutes: int
    up_threshold: float
    down_threshold: float
    confirmation_seconds: int
    entry_cutoff_seconds: int


class Settings(BaseSettings):
    app_name: str = "Crypto PolyMarket Trading Bot"
    app_mode: AppMode = AppMode.PAPER
    symbol: str = "BTCUSDT"
    db_path: Path = Path("data/trading_bot.db")
    reports_dir: Path = Path("data/reports")

    polymarket_market_slug: str | None = None
    polymarket_market_id: str | None = None

    up_threshold: float = Field(default=0.80, ge=0.0, le=1.0)
    down_threshold: float = Field(default=0.80, ge=0.0, le=1.0)
    confirmation_seconds: int = Field(default=20, ge=1)
    candle_minutes: int = Field(default=5, ge=1)
    entry_cutoff_seconds: int = Field(default=150, ge=1)

    five_minute_up_threshold: float = Field(default=0.90, ge=0.0, le=1.0)
    five_minute_down_threshold: float = Field(default=0.90, ge=0.0, le=1.0)
    five_minute_confirmation_seconds: int = Field(default=30, ge=1)
    five_minute_entry_cutoff_seconds: int = Field(default=60, ge=1)

    one_hour_up_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    one_hour_down_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    one_hour_confirmation_seconds: int = Field(default=120, ge=1)
    one_hour_entry_cutoff_seconds: int = Field(default=900, ge=1)

    fixed_notional_usd: float = Field(default=100.0, gt=0.0)
    fixed_margin_usd: float = Field(default=25.0, gt=0.0)
    leverage: int = Field(default=4, ge=1)

    backtest_fee_bps: float = Field(default=4.0, ge=0.0)
    backtest_slippage_bps: float = Field(default=0.0, ge=0.0)

    historical_months: int = Field(default=6, ge=1, le=24)
    polymarket_market_page_limit: int = Field(default=50, ge=1)
    polymarket_market_page_size: int = Field(default=100, ge=1, le=500)
    polymarket_history_fidelity_minutes: int = Field(default=1, ge=1)
    binance_kline_interval: str = "1m"

    binance_base_url: str = "https://fapi.binance.com"
    polymarket_gamma_base_url: str = "https://gamma-api.polymarket.com"
    polymarket_clob_base_url: str = "https://clob.polymarket.com"
    polymarket_ws_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    polymarket_dns_mode: str = "auto"
    polymarket_doh_url: str = "https://1.1.1.1/dns-query"

    streamlit_host: str = "127.0.0.1"
    streamlit_port: int = 8501

    binance_api_key: str | None = None
    binance_api_secret: str | None = None

    model_config = SettingsConfigDict(
        env_prefix="BOT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def strategy_profile(self, timeframe: str) -> StrategyProfile:
        if timeframe == "5m":
            return StrategyProfile(
                name="5m",
                candle_minutes=5,
                up_threshold=self.five_minute_up_threshold,
                down_threshold=self.five_minute_down_threshold,
                confirmation_seconds=self.five_minute_confirmation_seconds,
                entry_cutoff_seconds=self.five_minute_entry_cutoff_seconds,
            )
        if timeframe == "1h":
            return StrategyProfile(
                name="1h",
                candle_minutes=60,
                up_threshold=self.one_hour_up_threshold,
                down_threshold=self.one_hour_down_threshold,
                confirmation_seconds=self.one_hour_confirmation_seconds,
                entry_cutoff_seconds=self.one_hour_entry_cutoff_seconds,
            )
        raise ValueError(f"Unsupported timeframe: {timeframe}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
