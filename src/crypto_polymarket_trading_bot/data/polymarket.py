from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import websockets


class PolymarketClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def get_market_by_slug(self, slug: str) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
            response = await client.get(f"/markets/{slug}")
            response.raise_for_status()
            return dict(response.json())


class PolymarketMarketStream:
    def __init__(self, websocket_url: str) -> None:
        self.websocket_url = websocket_url

    async def subscribe(self, asset_ids: list[str]) -> AsyncIterator[dict[str, Any]]:
        async with websockets.connect(self.websocket_url) as websocket:
            await websocket.send(
                json.dumps(
                    {
                        "assets_ids": asset_ids,
                        "type": "market",
                        "custom_feature_enabled": True,
                    }
                )
            )
            async for message in websocket:
                yield {"raw": message}
