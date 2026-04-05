# AGENTS.md

## Mission

Build a Python-first trading system around a Polymarket BTC 5m signal and Binance Futures execution, while keeping strategy logic, execution, and backtesting independent from the Streamlit UI.

## Canonical Boundaries

- Keep all trading logic in Python modules under `src/crypto_polymarket_trading_bot/`.
- Keep Streamlit read-only in v1. It may display state, logs, charts, and summaries, but it must not own strategy logic.
- Preserve strict mode separation:
  - `backtest` for offline replay
  - `paper` for simulated execution
  - `live` for future real execution
- Reuse the same strategy engine across all modes.
- Persist runtime state in SQLite for v1.

## Locked Strategy Assumptions

- The signal source is the Polymarket BTC 5m market.
- `LONG` is confirmed when up odds remain `>= 0.70` for at least `10` consecutive seconds.
- `SHORT` is confirmed when up odds remain `<= 0.30` for at least `10` consecutive seconds.
- Only one position is allowed at a time.
- Position sizing uses fixed notional, fixed margin, and predefined leverage from config.
- The strategy does not flip intra-candle in v1.
- Positions close at the end of each 5m window.
- Each new 5m window is evaluated independently.

## Implementation Rules

- Prefer typed Python and explicit dataclasses or Pydantic models.
- Prefer thin internal client wrappers over SDK-heavy integration layers.
- Keep interfaces stable:
  - settings model
  - strategy decision contract
  - executor interface
  - SQLite repository contract
- Add tests when changing strategy behavior or repository writes.
- Avoid burying operational state in ad hoc globals; centralize it in strategy, executor, and repository objects.
- Treat live execution as opt-in and safety-gated.

## Safe Workflow Notes

- Build and validate in `backtest` and `paper` before adding live behavior.
- Do not introduce UI-driven side effects into Streamlit.
- Preserve local observability: every important signal, decision, and execution should be persistable and inspectable.
- When adding real Polymarket or Binance integrations, keep transport/parsing code inside `data/` and business logic inside `strategy/` or `execution/`.
