from crypto_polymarket_trading_bot.data import BinanceKline


def test_binance_kline_parsing() -> None:
    payload = [
        1711929600000,
        "70000.0",
        "70100.0",
        "69950.0",
        "70050.0",
        "123.45",
        1711929659999,
        "0",
        0,
        "0",
        "0",
        "0",
    ]
    kline = BinanceKline.from_api("BTCUSDT", "1m", payload)
    assert kline.symbol == "BTCUSDT"
    assert kline.interval == "1m"
    assert kline.open_price == 70000.0
    assert kline.close_price == 70050.0
