from __future__ import annotations

from typing import Any

import httpx


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
