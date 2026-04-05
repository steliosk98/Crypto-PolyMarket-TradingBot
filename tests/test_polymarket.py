from datetime import UTC, datetime
from pathlib import Path

from crypto_polymarket_trading_bot.data.polymarket import PolymarketMarket
from crypto_polymarket_trading_bot.storage import Repository


def test_polymarket_market_parsing() -> None:
    payload = {
        "id": 123,
        "slug": "btc-updown-5m-1775373600",
        "question": "BTC Up or Down in 5m?",
        "active": True,
        "closed": False,
        "acceptingOrders": True,
        "bestBid": "0.71",
        "bestAsk": "0.73",
        "lastTradePrice": "0.72",
        "outcomes": '["Yes", "No"]',
        "outcomePrices": '["0.72", "0.28"]',
        "clobTokenIds": '["token_yes", "token_no"]',
    }

    market = PolymarketMarket.from_api(payload)

    assert market.id == "123"
    assert market.slug == "btc-updown-5m-1775373600"
    assert market.outcomes == ["Yes", "No"]
    assert market.outcome_prices == [0.72, 0.28]
    assert market.clob_token_ids == ["token_yes", "token_no"]
    assert market.best_bid == 0.71
    assert market.best_ask == 0.73
    assert market.yes_price == 0.72
    assert market.no_price == 0.28
    assert market.yes_token_id == "token_yes"
    assert market.no_token_id == "token_no"


def test_polymarket_repository_storage(tmp_path: Path) -> None:
    repository = Repository(tmp_path / "market.db")
    market = PolymarketMarket(
        id="123",
        slug="btc-updown-5m-1775373600",
        question="BTC Up or Down in 5m?",
        active=True,
        closed=False,
        accepting_orders=True,
        best_bid=0.71,
        best_ask=0.73,
        last_trade_price=0.72,
        outcomes=["Yes", "No"],
        outcome_prices=[0.72, 0.28],
        clob_token_ids=["token_yes", "token_no"],
    )
    now = datetime(2026, 4, 5, 12, 0, tzinfo=UTC)

    repository.upsert_polymarket_market(market, now)
    repository.log_polymarket_snapshot(market, now)

    latest_market = repository.latest_polymarket_market()
    snapshots = repository.recent_polymarket_snapshots(limit=5)

    assert latest_market is not None
    assert latest_market["id"] == "123"
    assert latest_market["outcomes"] == ["Yes", "No"]
    assert latest_market["clob_token_ids"] == ["token_yes", "token_no"]
    assert snapshots[0]["yes_price"] == 0.72
    assert snapshots[0]["no_token_id"] == "token_no"
