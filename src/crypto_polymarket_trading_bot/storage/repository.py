from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from crypto_polymarket_trading_bot.data import PolymarketMarket
from crypto_polymarket_trading_bot.execution import ExecutionRecord, Position
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
                id, slug, question, active, closed, accepting_orders, best_bid, best_ask,
                last_trade_price, outcomes_json, outcome_prices_json, clob_token_ids_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                slug = excluded.slug,
                question = excluded.question,
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

    def log_signal_event(
        self,
        tick: OddsTick,
        candle_start: datetime,
        candidate_direction: SignalDirection | None,
        confirmation_progress_seconds: float,
    ) -> None:
        self._execute(
            """
            INSERT INTO signal_events (
                timestamp, market_id, up_odds, candle_start, candidate_direction, confirmation_progress_seconds
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
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
            """
            INSERT INTO decisions (
                timestamp, target_position, reason, up_odds, candle_start, candle_end, market_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
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
            """
            INSERT INTO executions (
                timestamp, action, side, status, fixed_notional_usd, fixed_margin_usd, leverage, market_id, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
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
                """
                INSERT INTO positions (
                    timestamp, side, status, fixed_notional_usd, fixed_margin_usd, leverage, market_id, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (timestamp.isoformat(), SignalDirection.FLAT.value, "CLOSED", 0.0, 0.0, 0, None, notes),
            )
            return

        self._execute(
            """
            INSERT INTO positions (
                timestamp, side, status, fixed_notional_usd, fixed_margin_usd, leverage, market_id, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
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

    def recent_polymarket_snapshots(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._fetchall(
            """
            SELECT timestamp, market_id, slug, best_bid, best_ask, last_trade_price,
                   yes_price, no_price, yes_token_id, no_token_id
            FROM polymarket_snapshots
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )

    def latest_polymarket_market(self) -> dict[str, Any] | None:
        rows = self._fetchall(
            """
            SELECT id, slug, question, active, closed, accepting_orders, best_bid, best_ask,
                   last_trade_price, outcomes_json, outcome_prices_json, clob_token_ids_json, updated_at
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

    def recent_decisions(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._fetchall(
            """
            SELECT timestamp, target_position, reason, up_odds, candle_start, candle_end, market_id
            FROM decisions
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )

    def recent_signal_events(self, limit: int = 200) -> list[dict[str, Any]]:
        return self._fetchall(
            """
            SELECT timestamp, market_id, up_odds, candle_start, candidate_direction, confirmation_progress_seconds
            FROM signal_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )

    def recent_executions(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._fetchall(
            """
            SELECT timestamp, action, side, status, fixed_notional_usd, fixed_margin_usd, leverage, market_id, details
            FROM executions
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )

    def latest_decision(self) -> dict[str, Any] | None:
        rows = self._fetchall(
            """
            SELECT timestamp, target_position, reason, up_odds, candle_start, candle_end, market_id
            FROM decisions
            ORDER BY id DESC
            LIMIT 1
            """
        )
        return rows[0] if rows else None

    def current_position(self) -> dict[str, Any] | None:
        rows = self._fetchall(
            """
            SELECT timestamp, side, status, fixed_notional_usd, fixed_margin_usd, leverage, market_id, notes
            FROM positions
            ORDER BY id DESC
            LIMIT 1
            """
        )
        return rows[0] if rows else None

    def counts(self) -> dict[str, int]:
        with self._connect() as connection:
            tables = [
                "polymarket_markets",
                "polymarket_snapshots",
                "signal_events",
                "decisions",
                "positions",
                "executions",
            ]
            return {
                table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in tables
            }

    def _execute(self, query: str, params: tuple[Any, ...]) -> None:
        with self._connect() as connection:
            connection.execute(query, params)
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
