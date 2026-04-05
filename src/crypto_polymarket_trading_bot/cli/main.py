from __future__ import annotations

import argparse
import asyncio
import csv
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import httpx

from crypto_polymarket_trading_bot.backtest import load_ticks_from_csv, run_backtest
from crypto_polymarket_trading_bot.config import Settings, get_settings
from crypto_polymarket_trading_bot.execution import PaperExecutor
from crypto_polymarket_trading_bot.historical import last_full_month_windows, run_monthly_backtests
from crypto_polymarket_trading_bot.ingestion import HistoricalDataService, PolymarketIngestionService
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
    market.add_argument("--db-path", type=Path, default=None)

    poly = subparsers.add_parser("fetch-polymarket-history", help="Fetch 6 months of BTC 5m Polymarket history.")
    poly.add_argument("--months", type=int, default=None)
    poly.add_argument("--db-path", type=Path, default=None)

    binance = subparsers.add_parser("fetch-binance-history", help="Fetch 6 months of Binance 1m futures klines.")
    binance.add_argument("--months", type=int, default=None)
    binance.add_argument("--db-path", type=Path, default=None)

    build = subparsers.add_parser("build-historical-dataset", help="Build normalized historical ticks from stored Polymarket and Binance history.")
    build.add_argument("--months", type=int, default=None)
    build.add_argument("--db-path", type=Path, default=None)

    monthly = subparsers.add_parser("backtest-monthly", help="Run monthly backtests from stored normalized historical ticks.")
    monthly.add_argument("--months", type=int, default=None)
    monthly.add_argument("--db-path", type=Path, default=None)
    monthly.add_argument("--export-format", choices=["csv", "json"], default=None)

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
        _print_basic_backtest(summary)
        return 0

    if args.command == "paper":
        runtime_settings = _with_db_override(settings, args.db_path)
        repository = Repository(Path(runtime_settings.db_path))
        ticks = load_ticks_from_csv(args.input)
        _run_paper_loop(ticks, runtime_settings, repository)
        print(f"Paper replay complete. Database updated at {runtime_settings.db_path}")
        return 0

    if args.command == "market-info":
        runtime_settings = _with_db_override(settings, args.db_path)
        repository = Repository(Path(runtime_settings.db_path))
        slug = args.slug or runtime_settings.polymarket_market_slug
        if not slug:
            parser.error("No market slug configured. Set BOT_POLYMARKET_MARKET_SLUG or pass --slug.")
        try:
            market = asyncio.run(_sync_market_info(runtime_settings, repository, slug))
        except httpx.HTTPError as exc:
            print(f"Failed to load Polymarket market '{slug}': {exc}")
            return 1
        print(f"Resolved market {market.id} slug={market.slug} yes_token_id={market.yes_token_id}")
        return 0

    if args.command == "fetch-polymarket-history":
        runtime_settings = _with_db_override(settings, args.db_path)
        months = args.months or runtime_settings.historical_months
        repository = Repository(Path(runtime_settings.db_path))
        try:
            result = asyncio.run(HistoricalDataService(runtime_settings, repository).fetch_polymarket_history(months))
        except httpx.HTTPError as exc:
            print(f"Failed to fetch Polymarket history: {exc}")
            return 1
        print(f"Fetched Polymarket markets={result['markets']} price_points={result['price_points']}")
        return 0

    if args.command == "fetch-binance-history":
        runtime_settings = _with_db_override(settings, args.db_path)
        months = args.months or runtime_settings.historical_months
        repository = Repository(Path(runtime_settings.db_path))
        try:
            result = asyncio.run(HistoricalDataService(runtime_settings, repository).fetch_binance_history(months))
        except httpx.HTTPError as exc:
            print(f"Failed to fetch Binance history: {exc}")
            return 1
        print(f"Fetched Binance klines={result['klines']}")
        return 0

    if args.command == "build-historical-dataset":
        runtime_settings = _with_db_override(settings, args.db_path)
        months = args.months or runtime_settings.historical_months
        repository = Repository(Path(runtime_settings.db_path))
        result = HistoricalDataService(runtime_settings, repository).build_historical_dataset(months)
        print(f"Built historical dataset ticks={result['ticks']}")
        return 0

    if args.command == "backtest-monthly":
        runtime_settings = _with_db_override(settings, args.db_path)
        months = args.months or runtime_settings.historical_months
        repository = Repository(Path(runtime_settings.db_path))
        windows = last_full_month_windows(months)
        ticks = repository.get_historical_ticks(windows[0].start, windows[-1].end)
        klines = repository.get_binance_klines(runtime_settings.symbol, runtime_settings.binance_kline_interval, windows[0].start, windows[-1].end)
        report = run_monthly_backtests(ticks, klines, runtime_settings, windows)
        run_id = repository.create_backtest_run(months, notes="monthly historical backtest")
        repository.save_backtest_report(run_id, report)
        _print_monthly_report(report)
        if args.export_format:
            _export_report(runtime_settings, run_id, report, args.export_format)
        return 0

    if args.command == "streamlit":
        host = args.host or settings.streamlit_host
        port = args.port or settings.streamlit_port
        module_path = Path(__file__).resolve().parents[1] / "app" / "dashboard.py"
        subprocess.run([
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(module_path),
            "--server.address",
            host,
            "--server.port",
            str(port),
        ], check=True)
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


def _print_basic_backtest(summary) -> None:
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


def _print_monthly_report(report) -> None:
    print("Monthly backtest summary")
    for row in report.monthly_summaries:
        print(
            f"month={row.month_key} trades_executed={row.trades_executed} skipped_trades={row.skipped_trades} "
            f"win_rate={row.win_rate:.4f} net_pnl_usd={row.net_pnl_usd:.4f}"
        )
    aggregate = report.aggregate_summary
    print("Aggregate summary")
    print(f"trades_attempted={aggregate.trades_attempted}")
    print(f"trades_executed={aggregate.trades_executed}")
    print(f"skipped_trades={aggregate.skipped_trades}")
    print(f"win_rate={aggregate.win_rate:.4f}")
    print(f"gross_pnl_usd={aggregate.gross_pnl_usd:.4f}")
    print(f"fees_usd={aggregate.fees_usd:.4f}")
    print(f"net_pnl_usd={aggregate.net_pnl_usd:.4f}")
    print(f"avg_trade_net_pnl_usd={aggregate.avg_trade_net_pnl_usd:.4f}")
    print(f"max_drawdown_usd={aggregate.max_drawdown_usd:.4f}")


def _export_report(settings: Settings, run_id: int, report, export_format: str) -> None:
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    if export_format == "json":
        path = settings.reports_dir / f"monthly_backtest_run_{run_id}.json"
        payload = {
            "monthly_summaries": [asdict(row) for row in report.monthly_summaries],
            "aggregate_summary": asdict(report.aggregate_summary),
            "trades": [asdict(row) for row in report.trades],
            "skipped_trades": [asdict(row) for row in report.skipped_trades],
        }
        path.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
        print(f"Exported report to {path}")
        return

    path = settings.reports_dir / f"monthly_backtest_run_{run_id}.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["month_key", "trades_executed", "skipped_trades", "win_rate", "net_pnl_usd"])
        writer.writeheader()
        for row in report.monthly_summaries:
            writer.writerow({
                "month_key": row.month_key,
                "trades_executed": row.trades_executed,
                "skipped_trades": row.skipped_trades,
                "win_rate": row.win_rate,
                "net_pnl_usd": row.net_pnl_usd,
            })
    print(f"Exported report to {path}")


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
