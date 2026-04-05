from __future__ import annotations

import socket
from collections.abc import Iterable
from typing import Any

import aiohttp
import httpx


class DohResolver(aiohttp.abc.AbstractResolver):
    def __init__(self, doh_url: str, timeout_seconds: float = 10.0) -> None:
        self.doh_url = doh_url
        self._client = httpx.AsyncClient(
            timeout=timeout_seconds,
            headers={"accept": "application/dns-json"},
        )

    async def resolve(
        self,
        host: str,
        port: int = 0,
        family: socket.AddressFamily = socket.AF_UNSPEC,
    ) -> list[dict[str, Any]]:
        record_type = "AAAA" if family == socket.AF_INET6 else "A"
        response = await self._client.get(self.doh_url, params={"name": host, "type": record_type})
        response.raise_for_status()
        payload = dict(response.json())
        ips = extract_answer_ips(payload.get("Answer", []), record_type)
        if not ips and record_type == "AAAA":
            response = await self._client.get(self.doh_url, params={"name": host, "type": "A"})
            response.raise_for_status()
            payload = dict(response.json())
            ips = extract_answer_ips(payload.get("Answer", []), "A")
            family = socket.AF_INET
        if not ips:
            raise OSError(f"DoH resolver returned no usable addresses for {host}")
        resolved_family = socket.AF_INET6 if family == socket.AF_INET6 else socket.AF_INET
        return [
            {
                "hostname": host,
                "host": ip,
                "port": port,
                "family": resolved_family,
                "proto": 0,
                "flags": socket.AI_NUMERICHOST,
            }
            for ip in ips
        ]

    async def close(self) -> None:
        await self._client.aclose()


def extract_answer_ips(answers: Iterable[dict[str, Any]], record_type: str) -> list[str]:
    expected_type = 28 if record_type == "AAAA" else 1
    ips: list[str] = []
    for answer in answers:
        if int(answer.get("type", 0)) != expected_type:
            continue
        data = str(answer.get("data", "")).strip()
        if data:
            ips.append(data)
    return ips
