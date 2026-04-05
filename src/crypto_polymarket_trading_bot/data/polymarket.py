from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx
import websockets


@dataclass(slots=True)
class PolymarketMarket:
    id: str
    slug: str | None
    question: str | None
    active: bool | None
    closed: bool | None
    accepting_orders: bool | None
    best_bid: float | None
    best_ask: float | None
    last_trade_price: float | None
    outcomes: list[str]
    outcome_prices: list[float]
    clob_token_ids: list[str]

    @property
    def yes_price(self) -> float | None:
        return self._outcome_price("yes")

    @property
    def no_price(self) -> float | None:
        return self._outcome_price("no")

    @property
    def yes_token_id(self) -> str | None:
        return self._token_id("yes")

    @property
    def no_token_id(self) -> str | None:
        return self._token_id("no")

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "PolymarketMarket":
        return cls(
            id=str(payload.get("id", "")),
            slug=payload.get("slug"),
            question=payload.get("question"),
            active=payload.get("active"),
            closed=payload.get("closed"),
            accepting_orders=payload.get("acceptingOrders"),
            best_bid=_maybe_float(payload.get("bestBid")),
            best_ask=_maybe_float(payload.get("bestAsk")),
            last_trade_price=_maybe_float(payload.get("lastTradePrice")),
            outcomes=_parse_string_list(payload.get("outcomes")),
            outcome_prices=_parse_float_list(payload.get("outcomePrices")),
            clob_token_ids=_parse_string_list(payload.get("clobTokenIds")),
        )

    def _outcome_price(self, outcome_name: str) -> float | None:
        for index, outcome in enumerate(self.outcomes):
            if outcome.strip().lower() == outcome_name and index < len(self.outcome_prices):
                return self.outcome_prices[index]
        return None

    def _token_id(self, outcome_name: str) -> str | None:
        for index, outcome in enumerate(self.outcomes):
            if outcome.strip().lower() == outcome_name and index < len(self.clob_token_ids):
                return self.clob_token_ids[index]
        return None


class PolymarketClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def get_market_by_slug(self, slug: str) -> PolymarketMarket:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
            response = await client.get(f"/markets/slug/{slug}")
            response.raise_for_status()
            payload = dict(response.json())
            return PolymarketMarket.from_api(payload)


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


def _parse_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return [part.strip() for part in stripped.split(",") if part.strip()]
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    return [str(value)]


def _parse_float_list(value: Any) -> list[float]:
    if value is None:
        return []
    if isinstance(value, list):
        return [float(item) for item in value]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return [float(part.strip()) for part in stripped.split(",") if part.strip()]
        if isinstance(parsed, list):
            return [float(item) for item in parsed]
    return [float(value)]


def _maybe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
