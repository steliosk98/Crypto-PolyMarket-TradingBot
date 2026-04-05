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
