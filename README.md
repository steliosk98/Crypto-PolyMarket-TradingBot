> [!WARNING]
> Backtests and proof-of-concept replays showed negative to minimal profits after fees, so this strategy is not worth proceeding with in its current form.

This project explored a simple systematic idea: use Polymarket BTC direction markets as a short-horizon signal for Binance Futures trades. The bot watches Polymarket odds for BTC going up or down over a fixed market window, waits for a strong threshold-based signal to persist for a short confirmation period, opens a fixed-size long or short on Binance, and closes the trade when that Polymarket market ends. The research focused on whether Polymarket conviction could translate into a profitable futures signal after execution costs.

# Crypto PolyMarket Trading Bot

Python trading bot scaffold for a BTC 5m strategy that reads Polymarket odds and drives Binance Futures decisions. The repository is intentionally split so trading logic, backtesting, execution, and storage live in Python modules, while Streamlit is used only as a read-only monitoring UI.

## Strategy v1

The current strategy contract is:

- Watch the Polymarket BTC 5m market.
- Confirm `LONG` if BTC up odds stay at or above `70%` for at least `10` consecutive seconds.
- Confirm `SHORT` if BTC down odds stay at or above `80%` for at least `20` consecutive seconds.
- Open one fixed-size Binance Futures position per 5m window.
- Hold until the end of that 5m window.
- Close at candle end.
- Re-evaluate the next 5m window from scratch.
- Do not flip intra-candle in v1.

The repository is optimized for `backtest` and `paper` modes first. `live` mode is scaffolded but not production-ready.

## Architecture

The package lives under `src/crypto_polymarket_trading_bot/`.

- `config/`: application settings, environment loading, shared constants.
- `data/`: thin API client wrappers for Polymarket and Binance.
- `strategy/`: threshold confirmation logic and 5m window state machine.
- `execution/`: paper executor plus live execution interface/stub.
- `backtest/`: CSV replay runner, trade simulation, and summary metrics.
- `storage/`: SQLite schema and repository helpers.
- `app/`: read-only Streamlit dashboard.
- `cli/`: command-line entrypoints for initialization and runtime modes.

## Setup

This project uses `uv` and a `src/` package layout.

```bash
uv sync
cp .env.example .env
```

Initialize the local database:

```bash
uv run cpmtb db-init
```

Run the included sample backtest:

```bash
uv run cpmtb backtest --input data/sample_ticks.csv
```

Run the paper-mode replay loop:

```bash
uv run cpmtb paper --input data/sample_ticks.csv
```

Launch the Streamlit dashboard:

```bash
uv run cpmtb streamlit
```

## Runtime Modes

- `backtest`: replay stored ticks, simulate entries/exits, and output trade metrics.
- `paper`: process ticks through the strategy and simulated executor while persisting run data locally.
- `live`: reserved for a future real-execution path.

## Environment Variables

All variables are loaded with the `BOT_` prefix.

- `BOT_APP_MODE`: `backtest`, `paper`, or `live`
- `BOT_SYMBOL`: Binance futures symbol, default `BTCUSDT`
- `BOT_DB_PATH`: SQLite database path, default `data/trading_bot.db`
- `BOT_POLYMARKET_MARKET_SLUG`: optional market slug
- `BOT_POLYMARKET_MARKET_ID`: optional direct market identifier
- `BOT_UP_THRESHOLD`: default `0.70`
- `BOT_DOWN_THRESHOLD`: default `0.30`
- `BOT_CONFIRMATION_SECONDS`: default `10`
- `BOT_CANDLE_MINUTES`: default `5`
- `BOT_FIXED_NOTIONAL_USD`: fixed notional size placeholder
- `BOT_FIXED_MARGIN_USD`: fixed margin placeholder
- `BOT_LEVERAGE`: predefined leverage placeholder
- `BOT_BACKTEST_FEE_BPS`: round-trip fee input is calculated from per-side bps, default `4.0`
- `BOT_BACKTEST_SLIPPAGE_BPS`: entry/exit slippage per side, default `0.0`
- `BOT_BINANCE_BASE_URL`: default Binance futures base URL
- `BOT_POLYMARKET_BASE_URL`: default Polymarket REST URL
- `BOT_POLYMARKET_WS_URL`: default Polymarket websocket URL
- `BOT_STREAMLIT_HOST`: dashboard host
- `BOT_STREAMLIT_PORT`: dashboard port

See `.env.example` for defaults.

## Data Contracts

The scaffold defines these core interfaces:

- `OddsTick`: timestamped Polymarket odds update with optional BTC reference price.
- `StrategyDecision`: target position (`LONG`, `SHORT`, `FLAT`) plus metadata.
- `Executor`: consumes decisions and produces execution records.
- `Repository`: persists signal events, decisions, positions, executions, and run summaries to SQLite.

## Backtesting Input

The replay runner expects CSV input with:

- `timestamp`: ISO 8601 timestamp
- `up_odds`: Polymarket BTC-up probability as a decimal
- `reference_price` or `btc_price`: BTC price used to simulate PnL
- `market_id`: optional identifier

The current backtest reports:

- completed trades
- win rate
- gross PnL
- fees
- net PnL
- average trade net PnL
- max drawdown

## Warning

This scaffold is not ready for unattended live trading. The live Binance executor is intentionally a stub. Use `backtest` and `paper` modes first, validate the signal, then harden execution, monitoring, and safety controls before any live deployment.
