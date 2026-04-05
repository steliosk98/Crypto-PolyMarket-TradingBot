from __future__ import annotations

from datetime import UTC, datetime

from crypto_polymarket_trading_bot.config import Settings
from crypto_polymarket_trading_bot.data import BinanceFuturesClient, PolymarketClient, PolymarketMarket, PolymarketPricePoint
from crypto_polymarket_trading_bot.historical import build_historical_ticks, last_full_month_windows
from crypto_polymarket_trading_bot.storage import Repository


class HistoricalDataService:
    def __init__(self, settings: Settings, repository: Repository) -> None:
        self.settings = settings
        self.repository = repository
        self.polymarket = PolymarketClient(
            settings.polymarket_gamma_base_url,
            settings.polymarket_clob_base_url,
            dns_mode=settings.polymarket_dns_mode,
            doh_url=settings.polymarket_doh_url,
        )
        self.binance = BinanceFuturesClient(settings.binance_base_url)

    async def fetch_polymarket_history(self, months: int) -> dict[str, int]:
        windows = last_full_month_windows(months)
        overall_start = windows[0].start
        overall_end = windows[-1].end
        markets = await self._discover_btc_5m_markets(overall_start, overall_end)
        fetched_points = 0
        fetched_markets = 0

        for market in markets:
            self.repository.upsert_polymarket_market(market, datetime.now(tz=UTC))
            if market.yes_token_id is None:
                continue
            history_start = max(market.start_date or overall_start, overall_start)
            history_end = min(market.end_date or overall_end, overall_end)
            if history_start >= history_end:
                continue
            points = await self.polymarket.get_prices_history(
                token_id=market.yes_token_id,
                start_ts=int(history_start.timestamp()),
                end_ts=int(history_end.timestamp()),
                fidelity=self.settings.polymarket_history_fidelity_minutes,
                market_id=market.id,
                market_slug=market.slug,
            )
            self.repository.insert_polymarket_history(points)
            fetched_markets += 1
            fetched_points += len(points)
        return {"markets": fetched_markets, "price_points": fetched_points}

    async def fetch_binance_history(self, months: int) -> dict[str, int]:
        windows = last_full_month_windows(months)
        overall_start_ms = int(windows[0].start.timestamp() * 1000)
        overall_end_ms = int(windows[-1].end.timestamp() * 1000)
        klines = []
        next_start = overall_start_ms

        while next_start < overall_end_ms:
            batch = await self.binance.get_klines(
                symbol=self.settings.symbol,
                interval=self.settings.binance_kline_interval,
                start_time_ms=next_start,
                end_time_ms=overall_end_ms,
            )
            if not batch:
                break
            klines.extend(batch)
            next_start = int(batch[-1].open_time.timestamp() * 1000) + 60_000

        self.repository.insert_binance_klines(klines)
        return {"klines": len(klines)}

    def build_historical_dataset(self, months: int) -> dict[str, int]:
        windows = last_full_month_windows(months)
        overall_start = windows[0].start
        overall_end = windows[-1].end
        points = self.repository.get_polymarket_history(overall_start, overall_end)
        klines = self.repository.get_binance_klines(self.settings.symbol, self.settings.binance_kline_interval, overall_start, overall_end)
        ticks = build_historical_ticks(points, klines)
        self.repository.replace_historical_ticks(ticks)
        return {"ticks": len(ticks)}

    async def _discover_btc_5m_markets(self, overall_start: datetime, overall_end: datetime) -> list[PolymarketMarket]:
        markets: list[PolymarketMarket] = []
        page_size = self.settings.polymarket_market_page_size
        for page in range(self.settings.polymarket_market_page_limit):
            batch = await self.polymarket.list_markets(limit=page_size, offset=page * page_size)
            if not batch:
                break
            for market in batch:
                if not _is_btc_5m_market(market):
                    continue
                market_end = market.end_date or overall_end
                market_start = market.start_date or overall_start
                if market_end < overall_start or market_start >= overall_end:
                    continue
                markets.append(market)
        unique: dict[str, PolymarketMarket] = {market.id: market for market in markets}
        return list(unique.values())


def _is_btc_5m_market(market: PolymarketMarket) -> bool:
    slug = (market.slug or "").lower()
    question = (market.question or "").lower()
    return slug.startswith("btc-updown-5m-") or ("btc" in question and "5m" in question)
