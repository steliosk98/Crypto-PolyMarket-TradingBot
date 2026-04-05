from __future__ import annotations

from pathlib import Path

import streamlit as st

from crypto_polymarket_trading_bot.config import get_settings
from crypto_polymarket_trading_bot.storage import Repository


def run_dashboard() -> None:
    settings = get_settings()
    repository = Repository(Path(settings.db_path))

    st.set_page_config(page_title=settings.app_name, layout="wide")
    st.title(settings.app_name)
    st.caption("Read-only dashboard for market ingestion, monthly backtests, and paper execution state.")

    counts = repository.counts()
    latest_market = repository.latest_polymarket_market()
    market_snapshots = repository.recent_polymarket_snapshots(limit=100)
    monthly_summaries = repository.latest_monthly_summaries()
    historical_trades = repository.latest_historical_trades(limit=100)
    skipped_trades = repository.latest_skipped_trades(limit=100)
    latest_decision = repository.latest_decision()
    current_position = repository.current_position()
    signal_events = repository.recent_signal_events(limit=200)
    recent_executions = repository.recent_executions(limit=25)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Markets", str(counts["polymarket_markets"]))
    col2.metric("Poly History", str(counts["polymarket_history"]))
    col3.metric("Binance 1m", str(counts["binance_klines"]))
    col4.metric("Hist Ticks", str(counts["historical_ticks"]))

    if monthly_summaries:
        aggregate = _aggregate_monthlies(monthly_summaries)
        st.subheader("Latest 6-Month Aggregate")
        agg1, agg2, agg3, agg4 = st.columns(4)
        agg1.metric("Trades Executed", str(aggregate["trades_executed"]))
        agg2.metric("Skipped Trades", str(aggregate["skipped_trades"]))
        agg3.metric("Win Rate", f"{aggregate['win_rate']:.2%}")
        agg4.metric("Net PnL", f"${aggregate['net_pnl_usd']:.2f}")

    st.subheader("Configured Polymarket Market")
    if latest_market is None:
        st.info("No Polymarket market metadata stored yet.")
    else:
        st.json(latest_market)

    if market_snapshots:
        latest_snapshot = market_snapshots[0]
        st.subheader("Latest Polymarket Snapshot")
        snap1, snap2, snap3, snap4 = st.columns(4)
        snap1.metric("Yes Price", _fmt_pct(latest_snapshot["yes_price"]))
        snap2.metric("No Price", _fmt_pct(latest_snapshot["no_price"]))
        snap3.metric("Best Bid", _fmt_pct(latest_snapshot["best_bid"]))
        snap4.metric("Best Ask", _fmt_pct(latest_snapshot["best_ask"]))

    st.subheader("Monthly Backtest Summaries")
    if monthly_summaries:
        st.dataframe(monthly_summaries, use_container_width=True)
        st.line_chart(monthly_summaries, x="month_key", y="net_pnl_usd")
    else:
        st.info("No monthly backtest summaries stored yet.")

    st.subheader("Historical Trades")
    st.dataframe(historical_trades, use_container_width=True)

    st.subheader("Skipped Trades")
    st.dataframe(skipped_trades, use_container_width=True)

    st.subheader("Current Position Snapshot")
    if current_position is None:
        st.info("No paper position snapshots recorded yet.")
    else:
        st.json(current_position)

    st.subheader("Latest Decision")
    if latest_decision is None:
        st.info("No strategy decisions recorded yet.")
    else:
        st.json(latest_decision)

    st.subheader("Recent Executions")
    st.dataframe(recent_executions, use_container_width=True)

    st.subheader("Recent Signal Events")
    st.dataframe(signal_events, use_container_width=True)


def _aggregate_monthlies(monthlies: list[dict[str, object]]) -> dict[str, float]:
    trades_executed = sum(int(row["trades_executed"]) for row in monthlies)
    skipped_trades = sum(int(row["skipped_trades"]) for row in monthlies)
    net_pnl_usd = sum(float(row["net_pnl_usd"]) for row in monthlies)
    winning_trades = sum(int(row["winning_trades"]) for row in monthlies)
    return {
        "trades_executed": float(trades_executed),
        "skipped_trades": float(skipped_trades),
        "net_pnl_usd": net_pnl_usd,
        "win_rate": (winning_trades / trades_executed) if trades_executed else 0.0,
    }


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2%}"


if __name__ == "__main__":
    run_dashboard()
