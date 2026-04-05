from __future__ import annotations

from datetime import UTC, datetime

from crypto_polymarket_trading_bot.config import Settings
from crypto_polymarket_trading_bot.data import PolymarketClient, PolymarketMarket
from crypto_polymarket_trading_bot.storage import Repository


class PolymarketIngestionService:
    def __init__(self, settings: Settings, repository: Repository) -> None:
        self.settings = settings
        self.repository = repository
        self.client = PolymarketClient(settings.polymarket_gamma_base_url, settings.polymarket_clob_base_url)

    async def sync_market_by_slug(self, slug: str) -> PolymarketMarket:
        market = await self.client.get_market_by_slug(slug)
        now = datetime.now(tz=UTC)
        self.repository.upsert_polymarket_market(market, now)
        self.repository.log_polymarket_snapshot(market, now)
        return market
