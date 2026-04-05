from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BacktestSummary:
    ticks_processed: int = 0
    decisions: int = 0
    entries: int = 0
    exits: int = 0
    long_entries: int = 0
    short_entries: int = 0
