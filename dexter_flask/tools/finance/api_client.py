"""Financial Datasets API — mirror src/tools/finance/api.ts."""
from __future__ import annotations

from typing import Any

import httpx

from dexter_flask.config import get_settings
from dexter_flask.tools.cache_util import read_cache, write_cache

BASE_URL = "https://api.financialdatasets.ai"


def strip_fields_deep(value: Any, fields: tuple[str, ...]) -> Any:
    drop = set(fields)
    if isinstance(value, list):
        return [strip_fields_deep(v, fields) for v in value]
    if not isinstance(value, dict):
        return value
    return {k: strip_fields_deep(v, fields) for k, v in value.items() if k not in drop}


class FinancialDatasetsClient:
    def __init__(self) -> None:
        self._key = (get_settings().financial_datasets_api_key or "").strip()

    def get(
        self,
        endpoint: str,
        params: dict[str, Any],
        *,
        cacheable: bool = False,
    ) -> tuple[dict[str, Any], str]:
        if cacheable:
            cached = read_cache(endpoint, params)
            if cached:
                return cached["data"], str(cached.get("url", ""))
        url = f"{BASE_URL}{endpoint}"
        headers = {"x-api-key": self._key} if self._key else {}
        with httpx.Client(timeout=120.0) as client:
            r = client.get(url, params=params, headers=headers)
            r.raise_for_status()
            data = r.json()
        full_url = str(r.url)
        if cacheable:
            write_cache(endpoint, params, data, full_url)
        return data, full_url

    def post(self, endpoint: str, body: dict[str, Any]) -> tuple[dict[str, Any], str]:
        url = f"{BASE_URL}{endpoint}"
        headers = {"Content-Type": "application/json", "x-api-key": self._key}
        with httpx.Client(timeout=120.0) as client:
            r = client.post(url, json=body, headers=headers)
            r.raise_for_status()
            data = r.json()
        return data, str(r.url)


_client: FinancialDatasetsClient | None = None


def get_api() -> FinancialDatasetsClient:
    global _client
    if _client is None:
        _client = FinancialDatasetsClient()
    return _client
