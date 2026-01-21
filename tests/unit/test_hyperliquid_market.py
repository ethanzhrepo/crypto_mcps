"""
hyperliquid_market tool unit tests
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.models import SourceMeta
from src.data_sources.hyperliquid.client import HyperliquidClient
from src.tools.hyperliquid_market import DEFAULT_FUNDING_LOOKBACK, HyperliquidMarketTool


@pytest.mark.asyncio
async def test_funding_default_start_time(monkeypatch):
    fixed_now = datetime(2026, 1, 21, 0, 0, 0, tzinfo=timezone.utc)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz else fixed_now.replace(tzinfo=None)

    monkeypatch.setattr("src.tools.hyperliquid_market.datetime", FixedDateTime)

    client = MagicMock(spec=HyperliquidClient)
    client.get_funding_history = AsyncMock(
        return_value=(
            [],
            SourceMeta(
                provider="hyperliquid",
                endpoint="/info",
                as_of_utc="2026-01-21T00:00:00Z",
                ttl_seconds=30,
            ),
        )
    )

    tool = HyperliquidMarketTool(hyperliquid_client=client)
    await tool.execute({"symbol": "BTC", "include_fields": ["funding"]})

    expected_start = int(
        fixed_now.timestamp() * 1000 - DEFAULT_FUNDING_LOOKBACK.total_seconds() * 1000
    )
    client.get_funding_history.assert_awaited_once()
    _, kwargs = client.get_funding_history.call_args
    assert kwargs["start_time"] == expected_start
    assert kwargs["end_time"] is None
