from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from crypto_polymarket_trading_bot.data import BinanceKline, PolymarketMarket, PolymarketPricePoint
from crypto_polymarket_trading_bot.execution import ExecutionRecord, Position
from crypto_polymarket_trading_bot.historical import HistoricalTick, HistoricalTrade, MonthlyBacktestReport, MonthlyBacktestSummary, SkippedTrade
from crypto_polymarket_trading_bot.strategy import OddsTick, SignalDirection, StrategyDecision

from .db import initialize_database


class Repository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        initialize_database(db_path)

    def upsert_polymarket_market(self, market: PolymarketMarket, timestamp: datetime) -> None:
        self._execute(
            """
            INSERT INTO polymarket_markets (
                id, slug, question, condition_id, start_date, end_date, active, closed, accepting_orders,
                best_bid, best_ask, last_trade_price, outcomes_json, outcome_prices_json,
                clob_token_ids_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                slug = excluded.slug,
                question = excluded.question,
                condition_id = excluded.condition_id,
                start_date = excluded.start_date,
                end_date = excluded.end_date,
                active = excluded.active,
                closed = excluded.closed,
                accepting_orders = excluded.accepting_orders,
                best_bid = excluded.best_bid,
                best_ask = excluded.best_ask,
                last_trade_price = excluded.last_trade_price,
                outcomes_json = excluded.outcomes_json,
                outcome_prices_json = excluded.outcome_prices_json,
                clob_token_ids_json = excluded.clob_token_ids_json,
                updated_at = excluded.updated_at
            """,
            (
                market.id,
                market.slug,
                market.question,
                market.condition_id,
                _iso_or_none(market.start_date),
                _iso_or_none(market.end_date),
                _bool_to_int(market.active),
                _bool_to_int(market.closed),
                _bool_to_int(market.accepting_orders),
                market.best_bid,
                market.best_ask,
                market.last_trade_price,
                json.dumps(market.outcomes),
                json.dumps(market.outcome_prices),
                json.dumps(market.clob_token_ids),
                timestamp.isoformat(),
            ),
        )

    def log_polymarket_snapshot(self, market: PolymarketMarket, timestamp: datetime) -> None:
        self._execute(
            """
            INSERT INTO polymarket_snapshots (
                timestamp, market_id, slug, best_bid, best_ask, last_trade_price,
                yes_price, no_price, yes_token_id, no_token_id, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp.isoformat(),
                market.id,
                market.slug,
                market.best_bid,
                market.best_ask,
                market.last_trade_price,
                market.yes_price,
                market.no_price,
                market.yes_token_id,
                market.no_token_id,
                json.dumps(
                    {
                        "id": market.id,
                        "slug": market.slug,
                        "question": market.question,
                        "active": market.active,
                        "closed": market.closed,
                        "accepting_orders": market.accepting_orders,
                        "best_bid": market.best_bid,
                        "best_ask": market.best_ask,
                        "last_trade_price": market.last_trade_price,
                        "outcomes": market.outcomes,
                        "outcome_prices": market.outcome_prices,
                        "clob_token_ids": market.clob_token_ids,
                    }
                ),
            ),
        )

    def insert_polymarket_history(self, points: list[PolymarketPricePoint], source: str = "prices-history") -> None:
        if not points:
            return
        self._executemany(
            """
            INSERT INTO polymarket_history (timestamp, market_id, market_slug, token_id, yes_price, source)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    point.timestamp.isoformat(),
                    point.market_id,
                    point.market_slug,
                    point.token_id,
                    point.price,
                    source,
                )
                for point in points
            ],
        )

    def insert_binance_klines(self, klines: list[BinanceKline]) -> None:
        if not klines:
            return
        self._executemany(
            """
            INSERT OR REPLACE INTO binance_klines (
                symbol, interval, open_time, close_time, open_price, high_price, low_price, close_price, volume
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.symbol,
                    row.interval,
                    row.open_time.isoformat(),
                    row.close_time.isoformat(),
                    row.open_price,
                    row.high_price,
                    row.low_price,
                    row.close_price,
                    row.volume,
                )
                for row in klines
            ],
        )

    def replace_historical_ticks(self, ticks: list[HistoricalTick]) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM historical_ticks")
            connection.executemany(
                """
                INSERT INTO historical_ticks (
                    timestamp, month_key, market_id, market_slug, up_odds_midpoint, best_bid_yes,
                    best_ask_yes, last_trade_yes, reference_price
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        tick.timestamp.isoformat(),
                        tick.month_key,
                        tick.market_id,
                        tick.market_slug,
                        tick.up_odds_midpoint,
                        tick.best_bid_yes,
                        tick.best_ask_yes,
                        tick.last_trade_yes,
                        tick.reference_price,
                    )
                    for tick in ticks
                ],
            )
            connection.commit()

    def create_backtest_run(self, months: int, notes: str = "") -> int:
        started_at = datetime.now(tz=UTC).isoformat()
        finished_at = started_at
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO backtest_runs (started_at, finished_at, months, notes) VALUES (?, ?, ?, ?)",
                (started_at, finished_at, months, notes),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def save_backtest_report(self, run_id: int, report: MonthlyBacktestReport) -> None:
        self._executemany(
            """
            INSERT INTO monthly_backtest_summaries (
                run_id, month_key, signal_points_total, signal_points_usable, binance_points, decisions,
                trades_attempted, trades_executed, skipped_trades, long_trades, short_trades,
                winning_trades, losing_trades, gross_pnl_usd, fees_usd, net_pnl_usd,
                avg_trade_net_pnl_usd, win_rate, max_drawdown_usd
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    row.month_key,
                    row.signal_points_total,
                    row.signal_points_usable,
                    row.binance_points,
                    row.decisions,
                    row.trades_attempted,
                    row.trades_executed,
                    row.skipped_trades,
                    row.long_trades,
                    row.short_trades,
                    row.winning_trades,
                    row.losing_trades,
                    row.gross_pnl_usd,
                    row.fees_usd,
                    row.net_pnl_usd,
                    row.avg_trade_net_pnl_usd,
                    row.win_rate,
                    row.max_drawdown_usd,
                )
                for row in report.monthly_summaries
            ],
        )
        self._executemany(
            """
            INSERT INTO historical_trades (
                run_id, month_key, side, market_id, market_slug, entry_time, planned_exit_time, exit_time,
                entry_price, exit_price, fixed_notional_usd, gross_pnl_usd, fees_usd, net_pnl_usd
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    row.month_key,
                    row.side.value,
                    row.market_id,
                    row.market_slug,
                    row.entry_time.isoformat(),
                    row.planned_exit_time.isoformat(),
                    row.exit_time.isoformat(),
                    row.entry_price,
                    row.exit_price,
                    row.fixed_notional_usd,
                    row.gross_pnl_usd,
                    row.fees_usd,
                    row.net_pnl_usd,
                )
                for row in report.trades
            ],
        )
        self._executemany(
            """
            INSERT INTO skipped_trades (run_id, month_key, timestamp, market_id, side, reason, details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    row.month_key,
                    row.timestamp.isoformat(),
                    row.market_id,
                    row.side.value,
                    row.reason,
                    row.details,
                )
                for row in report.skipped_trades
            ],
        )

    def list_polymarket_markets(self) -> list[dict[str, Any]]:
        rows = self._fetchall(
            "SELECT * FROM polymarket_markets ORDER BY start_date ASC"
        )
        for row in rows:
            row["outcomes"] = json.loads(row.pop("outcomes_json"))
            row["outcome_prices"] = json.loads(row.pop("outcome_prices_json"))
            row["clob_token_ids"] = json.loads(row.pop("clob_token_ids_json"))
        return rows

    def get_polymarket_history(self, start: datetime | None = None, end: datetime | None = None) -> list[PolymarketPricePoint]:
        query = "SELECT timestamp, market_id, market_slug, token_id, yes_price FROM polymarket_history"
        params: list[Any] = []
        clauses: list[str] = []
        if start is not None:
            clauses.append("timestamp >= ?")
            params.append(start.isoformat())
        if end is not None:
            clauses.append("timestamp < ?")
            params.append(end.isoformat())
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY timestamp ASC"
        rows = self._fetchall(query, tuple(params))
        return [
            PolymarketPricePoint(
                market_id=row["market_id"],
                market_slug=row["market_slug"],
                token_id=row["token_id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                price=float(row["yes_price"]),
            )
            for row in rows
        ]

    def get_binance_klines(self, symbol: str, interval: str, start: datetime | None = None, end: datetime | None = None) -> list[BinanceKline]:
        query = "SELECT * FROM binance_klines WHERE symbol = ? AND interval = ?"
        params: list[Any] = [symbol, interval]
        if start is not None:
            query += " AND open_time >= ?"
            params.append(start.isoformat())
        if end is not None:
            query += " AND open_time < ?"
            params.append(end.isoformat())
        query += " ORDER BY open_time ASC"
        rows = self._fetchall(query, tuple(params))
        return [
            BinanceKline(
                symbol=row["symbol"],
                interval=row["interval"],
                open_time=datetime.fromisoformat(row["open_time"]),
                close_time=datetime.fromisoformat(row["close_time"]),
                open_price=float(row["open_price"]),
                high_price=float(row["high_price"]),
                low_price=float(row["low_price"]),
                close_price=float(row["close_price"]),
                volume=float(row["volume"]),
            )
            for row in rows
        ]

    def get_historical_ticks(self, start: datetime | None = None, end: datetime | None = None) -> list[HistoricalTick]:
        query = "SELECT * FROM historical_ticks"
        params: list[Any] = []
        clauses: list[str] = []
        if start is not None:
            clauses.append("timestamp >= ?")
            params.append(start.isoformat())
        if end is not None:
            clauses.append("timestamp < ?")
            params.append(end.isoformat())
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY timestamp ASC"
        rows = self._fetchall(query, tuple(params))
        return [
            HistoricalTick(
                timestamp=datetime.fromisoformat(row["timestamp"]),
                month_key=row["month_key"],
                market_id=row["market_id"],
                market_slug=row["market_slug"],
                up_odds_midpoint=row["up_odds_midpoint"],
                best_bid_yes=row["best_bid_yes"],
                best_ask_yes=row["best_ask_yes"],
                last_trade_yes=row["last_trade_yes"],
                reference_price=row["reference_price"],
            )
            for row in rows
        ]

    def latest_backtest_run(self) -> dict[str, Any] | None:
        rows = self._fetchall("SELECT * FROM backtest_runs ORDER BY id DESC LIMIT 1")
        return rows[0] if rows else None

    def latest_monthly_summaries(self) -> list[dict[str, Any]]:
        run = self.latest_backtest_run()
        if run is None:
            return []
        return self._fetchall(
            "SELECT * FROM monthly_backtest_summaries WHERE run_id = ? ORDER BY month_key ASC",
            (run["id"],),
        )

    def latest_historical_trades(self, limit: int = 100) -> list[dict[str, Any]]:
        run = self.latest_backtest_run()
        if run is None:
            return []
        return self._fetchall(
            "SELECT * FROM historical_trades WHERE run_id = ? ORDER BY entry_time DESC LIMIT ?",
            (run["id"], limit),
        )

    def latest_skipped_trades(self, limit: int = 100) -> list[dict[str, Any]]:
        run = self.latest_backtest_run()
        if run is None:
            return []
        return self._fetchall(
            "SELECT * FROM skipped_trades WHERE run_id = ? ORDER BY timestamp DESC LIMIT ?",
            (run["id"], limit),
        )

    def latest_polymarket_market(self) -> dict[str, Any] | None:
        rows = self._fetchall(
            """
            SELECT id, slug, question, condition_id, start_date, end_date, active, closed, accepting_orders,
                   best_bid, best_ask, last_trade_price, outcomes_json, outcome_prices_json, clob_token_ids_json, updated_at
            FROM polymarket_markets
            ORDER BY updated_at DESC
            LIMIT 1
            """
        )
        if not rows:
            return None
        row = rows[0]
        row["outcomes"] = json.loads(row.pop("outcomes_json"))
        row["outcome_prices"] = json.loads(row.pop("outcome_prices_json"))
        row["clob_token_ids"] = json.loads(row.pop("clob_token_ids_json"))
        return row

    def recent_polymarket_snapshots(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._fetchall(
            "SELECT timestamp, market_id, slug, best_bid, best_ask, last_trade_price, yes_price, no_price, yes_token_id, no_token_id FROM polymarket_snapshots ORDER BY id DESC LIMIT ?",
            (limit,),
        )

    def log_signal_event(
        self,
        tick: OddsTick,
        candle_start: datetime,
        candidate_direction: SignalDirection | None,
        confirmation_progress_seconds: float,
    ) -> None:
        self._execute(
            "INSERT INTO signal_events (timestamp, market_id, up_odds, candle_start, candidate_direction, confirmation_progress_seconds) VALUES (?, ?, ?, ?, ?, ?)",
            (
                tick.timestamp.isoformat(),
                tick.market_id,
                tick.up_odds,
                candle_start.isoformat(),
                candidate_direction.value if candidate_direction is not None else None,
                confirmation_progress_seconds,
            ),
        )

    def log_decision(self, decision: StrategyDecision) -> None:
        self._execute(
            "INSERT INTO decisions (timestamp, target_position, reason, up_odds, candle_start, candle_end, market_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                decision.timestamp.isoformat(),
                decision.target_position.value,
                decision.reason,
                decision.up_odds,
                decision.candle_start.isoformat(),
                decision.candle_end.isoformat(),
                decision.market_id,
            ),
        )

    def log_execution(self, record: ExecutionRecord) -> None:
        self._execute(
            "INSERT INTO executions (timestamp, action, side, status, fixed_notional_usd, fixed_margin_usd, leverage, market_id, details) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.timestamp.isoformat(),
                record.action,
                record.side.value,
                record.status,
                record.fixed_notional_usd,
                record.fixed_margin_usd,
                record.leverage,
                record.market_id,
                record.details,
            ),
        )

    def log_position_snapshot(self, position: Position | None, timestamp: datetime, notes: str = "") -> None:
        if position is None:
            self._execute(
                "INSERT INTO positions (timestamp, side, status, fixed_notional_usd, fixed_margin_usd, leverage, market_id, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (timestamp.isoformat(), SignalDirection.FLAT.value, "CLOSED", 0.0, 0.0, 0, None, notes),
            )
            return
        self._execute(
            "INSERT INTO positions (timestamp, side, status, fixed_notional_usd, fixed_margin_usd, leverage, market_id, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                timestamp.isoformat(),
                position.side.value,
                "OPEN",
                position.fixed_notional_usd,
                position.fixed_margin_usd,
                position.leverage,
                position.market_id,
                notes,
            ),
        )

    def recent_decisions(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._fetchall("SELECT timestamp, target_position, reason, up_odds, candle_start, candle_end, market_id FROM decisions ORDER BY id DESC LIMIT ?", (limit,))

    def recent_signal_events(self, limit: int = 200) -> list[dict[str, Any]]:
        return self._fetchall("SELECT timestamp, market_id, up_odds, candle_start, candidate_direction, confirmation_progress_seconds FROM signal_events ORDER BY id DESC LIMIT ?", (limit,))

    def recent_executions(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._fetchall("SELECT timestamp, action, side, status, fixed_notional_usd, fixed_margin_usd, leverage, market_id, details FROM executions ORDER BY id DESC LIMIT ?", (limit,))

    def latest_decision(self) -> dict[str, Any] | None:
        rows = self._fetchall("SELECT timestamp, target_position, reason, up_odds, candle_start, candle_end, market_id FROM decisions ORDER BY id DESC LIMIT 1")
        return rows[0] if rows else None

    def current_position(self) -> dict[str, Any] | None:
        rows = self._fetchall("SELECT timestamp, side, status, fixed_notional_usd, fixed_margin_usd, leverage, market_id, notes FROM positions ORDER BY id DESC LIMIT 1")
        return rows[0] if rows else None

    def counts(self) -> dict[str, int]:
        with self._connect() as connection:
            tables = [
                "polymarket_markets",
                "polymarket_snapshots",
                "polymarket_history",
                "binance_klines",
                "historical_ticks",
                "backtest_runs",
                "monthly_backtest_summaries",
                "historical_trades",
                "skipped_trades",
                "signal_events",
                "decisions",
                "positions",
                "executions",
            ]
            return {table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in tables}

    def _execute(self, query: str, params: tuple[Any, ...]) -> None:
        with self._connect() as connection:
            connection.execute(query, params)
            connection.commit()

    def _executemany(self, query: str, params: list[tuple[Any, ...]]) -> None:
        if not params:
            return
        with self._connect() as connection:
            connection.executemany(query, params)
            connection.commit()

    def _fetchall(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)


def _bool_to_int(value: bool | None) -> int | None:
    if value is None:
        return None
    return int(value)


def _iso_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
