"""
Hyperliquid public API client.

Docs: https://hyperliquid.gitbook.io/hyperliquid-docs/api
"""
from datetime import datetime
from typing import Any, Dict, Optional

from src.core.models import SourceMeta
from src.data_sources.base import BaseDataSource


class HyperliquidClient(BaseDataSource):
    """Hyperliquid public API client (no auth required)."""

    BASE_URL = "https://api.hyperliquid.xyz"

    def __init__(self):
        super().__init__(
            name="hyperliquid",
            base_url=self.BASE_URL,
            timeout=10.0,
            requires_api_key=False,
        )

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def fetch_raw(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        base_url_override: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Hyperliquid uses POST with JSON bodies for /info."""
        payload = params or {}
        return await self._make_request(
            "POST",
            endpoint,
            base_url_override=base_url_override,
            headers=headers,
            json_body=payload,
        )

    def transform(self, raw_data: Any, data_type: str) -> Dict[str, Any]:
        return raw_data

    async def get_info(
        self,
        payload: Dict[str, Any],
        ttl_seconds: int = 5,
    ) -> tuple[Any, SourceMeta]:
        """Generic /info call for arbitrary payloads."""
        data, meta = await self.fetch(
            endpoint="/info",
            params=payload,
            data_type="raw",
            ttl_seconds=ttl_seconds,
        )
        return data, meta

    async def get_l2_book(
        self,
        coin: str,
        ttl_seconds: int = 2,
    ) -> tuple[Any, SourceMeta]:
        return await self.get_info({"type": "l2Book", "coin": coin}, ttl_seconds)

    async def get_recent_trades(
        self,
        coin: str,
        ttl_seconds: int = 5,
    ) -> tuple[Any, SourceMeta]:
        return await self.get_info({"type": "recentTrades", "coin": coin}, ttl_seconds)

    async def get_funding_history(
        self,
        coin: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        ttl_seconds: int = 30,
    ) -> tuple[Any, SourceMeta]:
        payload = {"type": "fundingHistory", "coin": coin}
        if start_time is not None:
            payload["startTime"] = start_time
        if end_time is not None:
            payload["endTime"] = end_time
        return await self.get_info(payload, ttl_seconds)

    async def get_open_interest(
        self,
        coin: str,
        ttl_seconds: int = 10,
    ) -> tuple[Any, SourceMeta]:
        return await self.get_info({"type": "openInterest", "coin": coin}, ttl_seconds)

    async def get_meta(
        self,
        ttl_seconds: int = 300,
    ) -> tuple[Any, SourceMeta]:
        return await self.get_info({"type": "meta"}, ttl_seconds)

    async def get_asset_contexts(
        self,
        ttl_seconds: int = 10,
    ) -> tuple[Any, SourceMeta]:
        return await self.get_info({"type": "metaAndAssetCtxs"}, ttl_seconds)
