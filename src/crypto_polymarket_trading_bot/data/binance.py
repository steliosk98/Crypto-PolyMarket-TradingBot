from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx


@dataclass(slots=True)
class BinanceKline:
    symbol: str
    interval: str
    open_time: datetime
    close_time: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float

    @classmethod
    def from_api(cls, symbol: str, interval: str, payload: list[Any]) -> "BinanceKline":
        return cls(
            symbol=symbol,
            interval=interval,
            open_time=datetime.fromtimestamp(int(payload[0]) / 1000, tz=UTC),
            close_time=datetime.fromtimestamp(int(payload[6]) / 1000, tz=UTC),
            open_price=float(payload[1]),
            high_price=float(payload[2]),
            low_price=float(payload[3]),
            close_price=float(payload[4]),
            volume=float(payload[5]),
        )


class BinanceFuturesClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def exchange_info(self) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
            response = await client.get("/fapi/v1/exchangeInfo")
            response.raise_for_status()
            return dict(response.json())

    async def ping(self) -> bool:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
            response = await client.get("/fapi/v1/ping")
            response.raise_for_status()
            return True

    async def get_klines(
        self,
        symbol: str,
        interval: str,
        start_time_ms: int,
        end_time_ms: int,
        limit: int = 1500,
    ) -> list[BinanceKline]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=20.0) as client:
            response = await client.get(
                "/fapi/v1/klines",
                params={
                    "symbol": symbol,
                    "interval": interval,
                    "startTime": start_time_ms,
                    "endTime": end_time_ms,
                    "limit": limit,
                },
            )
            response.raise_for_status()
            payload = list(response.json())
            return [BinanceKline.from_api(symbol, interval, row) for row in payload]
