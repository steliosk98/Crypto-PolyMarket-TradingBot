from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

import httpx

from crypto_polymarket_trading_bot.backtest import load_ticks_from_csv, run_backtest
from crypto_polymarket_trading_bot.config import Settings, get_settings
from crypto_polymarket_trading_bot.execution import PaperExecutor
from crypto_polymarket_trading_bot.ingestion import PolymarketIngestionService
from crypto_polymarket_trading_bot.storage import Repository, initialize_database
from crypto_polymarket_trading_bot.strategy import OddsTick, StrategyEngine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cpmtb", description="Crypto PolyMarket Trading Bot CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    db_init = subparsers.add_parser("db-init", help="Initialize the SQLite database.")
    db_init.add_argument("--db-path", type=Path, default=None)

    backtest = subparsers.add_parser("backtest", help="Replay a CSV file through the strategy engine.")
    backtest.add_argument("--input", type=Path, required=True)
    backtest.add_argument("--db-path", type=Path, default=None)

    paper = subparsers.add_parser("paper", help="Replay ticks and persist paper decisions/executions.")
    paper.add_argument("--input", type=Path, required=True)
    paper.add_argument("--db-path", type=Path, default=None)

    market = subparsers.add_parser("market-info", help="Resolve the configured Polymarket market slug.")
    market.add_argument("--slug", default=None)

    streamlit = subparsers.add_parser("streamlit", help="Launch the read-only Streamlit dashboard.")
    streamlit.add_argument("--host", default=None)
    streamlit.add_argument("--port", type=int, default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = get_settings()

    if args.command == "db-init":
        db_path = args.db_path or Path(settings.db_path)
        initialize_database(db_path)
        print(f"Initialized database at {db_path}")
        return 0

    if args.command == "backtest":
        runtime_settings = _with_db_override(settings, args.db_path)
        ticks = load_ticks_from_csv(args.input)
        summary = run_backtest(ticks, runtime_settings)
        print("Backtest summary")
        print(f"ticks_processed={summary.ticks_processed}")
        print(f"decisions={summary.decisions}")
        print(f"entries={summary.entries}")
        print(f"exits={summary.exits}")
        print(f"long_entries={summary.long_entries}")
        print(f"short_entries={summary.short_entries}")
        print(f"completed_trades={summary.completed_trades}")
        print(f"winning_trades={summary.winning_trades}")
        print(f"losing_trades={summary.losing_trades}")
        print(f"win_rate={summary.win_rate:.4f}")
        print(f"gross_pnl_usd={summary.gross_pnl_usd:.4f}")
        print(f"fees_usd={summary.fees_usd:.4f}")
        print(f"net_pnl_usd={summary.net_pnl_usd:.4f}")
        print(f"avg_trade_net_pnl_usd={summary.avg_trade_net_pnl_usd:.4f}")
        print(f"max_drawdown_usd={summary.max_drawdown_usd:.4f}")
        return 0

    if args.command == "paper":
        runtime_settings = _with_db_override(settings, args.db_path)
        repository = Repository(Path(runtime_settings.db_path))
        ticks = load_ticks_from_csv(args.input)
        _run_paper_loop(ticks, runtime_settings, repository)
        print(f"Paper replay complete. Database updated at {runtime_settings.db_path}")
        return 0

    if args.command == "market-info":
        runtime_settings = _with_db_override(settings, None)
        repository = Repository(Path(runtime_settings.db_path))
        slug = args.slug or runtime_settings.polymarket_market_slug
        if not slug:
            parser.error("No market slug configured. Set BOT_POLYMARKET_MARKET_SLUG or pass --slug.")
        try:
            market = asyncio.run(_sync_market_info(runtime_settings, repository, slug))
        except httpx.HTTPError as exc:
            print(f"Failed to load Polymarket market '{slug}': {exc}")
            return 1
        print("Polymarket market")
        print(f"id={market.id}")
        print(f"slug={market.slug}")
        print(f"question={market.question}")
        print(f"active={market.active}")
        print(f"closed={market.closed}")
        print(f"accepting_orders={market.accepting_orders}")
        print(f"best_bid={market.best_bid}")
        print(f"best_ask={market.best_ask}")
        print(f"last_trade_price={market.last_trade_price}")
        print(f"outcomes={market.outcomes}")
        print(f"outcome_prices={market.outcome_prices}")
        print(f"clob_token_ids={market.clob_token_ids}")
        print(f"yes_price={market.yes_price}")
        print(f"no_price={market.no_price}")
        print(f"yes_token_id={market.yes_token_id}")
        print(f"no_token_id={market.no_token_id}")
        return 0

    if args.command == "streamlit":
        host = args.host or settings.streamlit_host
        port = args.port or settings.streamlit_port
        module_path = Path(__file__).resolve().parents[1] / "app" / "dashboard.py"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(module_path),
                "--server.address",
                host,
                "--server.port",
                str(port),
            ],
            check=True,
        )
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


async def _sync_market_info(settings: Settings, repository: Repository, slug: str):
    service = PolymarketIngestionService(settings, repository)
    return await service.sync_market_by_slug(slug)


def _with_db_override(settings: Settings, db_path: Path | None) -> Settings:
    if db_path is None:
        return settings
    return settings.model_copy(update={"db_path": db_path})


def _run_paper_loop(ticks: list[OddsTick], settings: Settings, repository: Repository) -> None:
    engine = StrategyEngine(settings)
    executor = PaperExecutor(settings)

    for tick in ticks:
        candle_start, candidate_direction, progress = engine.classify_tick(tick)
        repository.log_signal_event(tick, candle_start, candidate_direction, progress)

        decisions = engine.process_tick(tick)
        for decision in decisions:
            repository.log_decision(decision)
            execution_records = executor.handle_decision(decision)
            for record in execution_records:
                repository.log_execution(record)
            repository.log_position_snapshot(executor.current_position, decision.timestamp, decision.reason)


if __name__ == "__main__":
    raise SystemExit(main())
