from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TEXT NOT NULL,
        mode TEXT NOT NULL,
        notes TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS polymarket_markets (
        id TEXT PRIMARY KEY,
        slug TEXT,
        question TEXT,
        condition_id TEXT,
        start_date TEXT,
        end_date TEXT,
        active INTEGER,
        closed INTEGER,
        accepting_orders INTEGER,
        best_bid REAL,
        best_ask REAL,
        last_trade_price REAL,
        outcomes_json TEXT NOT NULL,
        outcome_prices_json TEXT NOT NULL,
        clob_token_ids_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS polymarket_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        market_id TEXT NOT NULL,
        slug TEXT,
        best_bid REAL,
        best_ask REAL,
        last_trade_price REAL,
        yes_price REAL,
        no_price REAL,
        yes_token_id TEXT,
        no_token_id TEXT,
        raw_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS polymarket_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        market_id TEXT NOT NULL,
        market_slug TEXT,
        token_id TEXT NOT NULL,
        yes_price REAL NOT NULL,
        source TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS binance_klines (
        symbol TEXT NOT NULL,
        interval TEXT NOT NULL,
        open_time TEXT NOT NULL,
        close_time TEXT NOT NULL,
        open_price REAL NOT NULL,
        high_price REAL NOT NULL,
        low_price REAL NOT NULL,
        close_price REAL NOT NULL,
        volume REAL NOT NULL,
        PRIMARY KEY(symbol, interval, open_time)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS historical_ticks (
        timestamp TEXT NOT NULL,
        month_key TEXT NOT NULL,
        market_id TEXT NOT NULL,
        market_slug TEXT,
        up_odds_midpoint REAL,
        best_bid_yes REAL,
        best_ask_yes REAL,
        last_trade_yes REAL,
        reference_price REAL,
        PRIMARY KEY(timestamp, market_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TEXT NOT NULL,
        finished_at TEXT NOT NULL,
        months INTEGER NOT NULL,
        notes TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS monthly_backtest_summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        month_key TEXT NOT NULL,
        signal_points_total INTEGER NOT NULL,
        signal_points_usable INTEGER NOT NULL,
        binance_points INTEGER NOT NULL,
        decisions INTEGER NOT NULL,
        trades_attempted INTEGER NOT NULL,
        trades_executed INTEGER NOT NULL,
        skipped_trades INTEGER NOT NULL,
        long_trades INTEGER NOT NULL,
        short_trades INTEGER NOT NULL,
        winning_trades INTEGER NOT NULL,
        losing_trades INTEGER NOT NULL,
        gross_pnl_usd REAL NOT NULL,
        fees_usd REAL NOT NULL,
        net_pnl_usd REAL NOT NULL,
        avg_trade_net_pnl_usd REAL NOT NULL,
        win_rate REAL NOT NULL,
        max_drawdown_usd REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS historical_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        month_key TEXT NOT NULL,
        side TEXT NOT NULL,
        market_id TEXT,
        market_slug TEXT,
        entry_time TEXT NOT NULL,
        planned_exit_time TEXT NOT NULL,
        exit_time TEXT NOT NULL,
        entry_price REAL NOT NULL,
        exit_price REAL NOT NULL,
        fixed_notional_usd REAL NOT NULL,
        gross_pnl_usd REAL NOT NULL,
        fees_usd REAL NOT NULL,
        net_pnl_usd REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS skipped_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        month_key TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        market_id TEXT,
        side TEXT NOT NULL,
        reason TEXT NOT NULL,
        details TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS signal_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        market_id TEXT,
        up_odds REAL NOT NULL,
        candle_start TEXT NOT NULL,
        candidate_direction TEXT,
        confirmation_progress_seconds REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        target_position TEXT NOT NULL,
        reason TEXT NOT NULL,
        up_odds REAL NOT NULL,
        candle_start TEXT NOT NULL,
        candle_end TEXT NOT NULL,
        market_id TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        side TEXT NOT NULL,
        status TEXT NOT NULL,
        fixed_notional_usd REAL NOT NULL,
        fixed_margin_usd REAL NOT NULL,
        leverage INTEGER NOT NULL,
        market_id TEXT,
        notes TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS executions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        action TEXT NOT NULL,
        side TEXT NOT NULL,
        status TEXT NOT NULL,
        fixed_notional_usd REAL NOT NULL,
        fixed_margin_usd REAL NOT NULL,
        leverage INTEGER NOT NULL,
        market_id TEXT,
        details TEXT
    )
    """,
)


def initialize_database(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        connection.commit()
