"""
Binance Options API client.

Public endpoints under eapi/v1 (no auth required for market data).
"""
from typing import Any, Dict, Optional

from src.core.models import SourceMeta
from src.data_sources.base import BaseDataSource


class BinanceOptionsClient(BaseDataSource):
    """Binance Options REST API client."""

    BASE_URL = "https://eapi.binance.com"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            name="binance_options",
            base_url=self.BASE_URL,
            timeout=10.0,
            requires_api_key=False,
        )
        if api_key:
            self.api_key = api_key

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
        }
        if self.api_key:
            headers["X-MBX-APIKEY"] = self.api_key
        return headers

    async def fetch_raw(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        base_url_override: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        return await self._make_request("GET", endpoint, params, base_url_override, headers)

    def transform(self, raw_data: Any, data_type: str) -> Dict[str, Any]:
        return raw_data

    async def get_exchange_info(
        self,
        symbol: Optional[str] = None,
    ) -> tuple[Any, SourceMeta]:
        endpoint = "/eapi/v1/exchangeInfo"
        params = {}
        if symbol:
            params["symbol"] = symbol
        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="raw",
            ttl_seconds=3600,
        )

    async def get_mark_data(
        self,
        symbol: Optional[str] = None,
    ) -> tuple[Any, SourceMeta]:
        endpoint = "/eapi/v1/mark"
        params = {}
        if symbol:
            params["symbol"] = symbol
        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="raw",
            ttl_seconds=30,
        )

    async def get_ticker(
        self,
        symbol: Optional[str] = None,
    ) -> tuple[Any, SourceMeta]:
        endpoint = "/eapi/v1/ticker"
        params = {}
        if symbol:
            params["symbol"] = symbol
        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="raw",
            ttl_seconds=30,
        )
