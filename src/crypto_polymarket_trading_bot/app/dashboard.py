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
    st.caption("Read-only monitoring dashboard for strategy state, decisions, and paper executions.")

    counts = repository.counts()
    latest_market = repository.latest_polymarket_market()
    market_snapshots = repository.recent_polymarket_snapshots(limit=100)
    latest_decision = repository.latest_decision()
    current_position = repository.current_position()
    signal_events = repository.recent_signal_events(limit=200)
    recent_decisions = repository.recent_decisions(limit=25)
    recent_executions = repository.recent_executions(limit=25)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Mode", settings.app_mode.value)
    col2.metric("Markets", str(counts["polymarket_markets"]))
    col3.metric("Signals", str(counts["signal_events"]))
    col4.metric("Executions", str(counts["executions"]))

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

    st.subheader("Latest Decision")
    if latest_decision is None:
        st.info("No strategy decisions recorded yet.")
    else:
        st.json(latest_decision)

    st.subheader("Current Position Snapshot")
    if current_position is None:
        st.info("No paper position snapshots recorded yet.")
    else:
        st.json(current_position)

    if signal_events:
        latest_signal = signal_events[0]
        st.subheader("Latest Signal State")
        sig1, sig2, sig3 = st.columns(3)
        sig1.metric("Up Odds", f"{latest_signal['up_odds']:.2%}")
        sig2.metric("Candidate", latest_signal["candidate_direction"] or "NONE")
        sig3.metric("Confirm Progress", f"{latest_signal['confirmation_progress_seconds']:.1f}s")

    st.subheader("Recent Market Snapshots")
    st.dataframe(market_snapshots, use_container_width=True)
    if market_snapshots:
        chart_points = list(reversed(market_snapshots))
        st.line_chart(
            data=[
                {
                    "timestamp": row["timestamp"],
                    "yes_price": row["yes_price"],
                    "no_price": row["no_price"],
                }
                for row in chart_points
            ],
            x="timestamp",
            y=["yes_price", "no_price"],
        )

    st.subheader("Recent Decisions")
    st.dataframe(recent_decisions, use_container_width=True)

    st.subheader("Recent Executions")
    st.dataframe(recent_executions, use_container_width=True)

    st.subheader("Recent Signal Events")
    st.dataframe(signal_events, use_container_width=True)
    if signal_events:
        chart_points = list(reversed(signal_events))
        st.line_chart(
            data=[{"timestamp": row["timestamp"], "up_odds": row["up_odds"]} for row in chart_points],
            x="timestamp",
            y="up_odds",
        )


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2%}"


if __name__ == "__main__":
    run_dashboard()
