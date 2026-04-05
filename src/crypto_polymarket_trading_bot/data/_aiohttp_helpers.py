from __future__ import annotations

import socket

import aiohttp

from crypto_polymarket_trading_bot.data.doh import DohResolver


def build_connector(
    use_doh: bool,
    doh_url: str,
    *,
    ipv4_only: bool = True,
) -> tuple[aiohttp.TCPConnector, DohResolver | None]:
    resolver = DohResolver(doh_url) if use_doh else None
    family = socket.AF_INET if ipv4_only else socket.AF_UNSPEC
    return aiohttp.TCPConnector(resolver=resolver, family=family), resolver
