"""
Flashbots / MEV-Boost data client (public relay stats).

Endpoints are served by Flashbots relay. No API key required.
"""
from typing import Any, Dict, Optional

from src.core.models import SourceMeta
from src.data_sources.base import BaseDataSource


class FlashbotsMevClient(BaseDataSource):
    """Flashbots MEV-Boost relay stats client."""

    BASE_URL = "https://boost-relay.flashbots.net"

    def __init__(self):
        super().__init__(
            name="flashbots",
            base_url=self.BASE_URL,
            timeout=10.0,
            requires_api_key=False,
        )

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json",
        }

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

    async def get_builder_blocks_received(
        self,
        limit: int = 100,
    ) -> tuple[Any, SourceMeta]:
        endpoint = "/relay/v1/data/bidtraces/builder_blocks_received"
        params = {"limit": min(limit, 500)}
        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="raw",
            ttl_seconds=30,
        )

    async def get_proposer_payload_delivered(
        self,
        limit: int = 100,
    ) -> tuple[Any, SourceMeta]:
        endpoint = "/relay/v1/data/bidtraces/proposer_payload_delivered"
        params = {"limit": min(limit, 500)}
        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="raw",
            ttl_seconds=30,
        )
