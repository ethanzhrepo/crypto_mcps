"""
crypto_news_search 工具单元测试
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.models import SourceMeta, CryptoNewsSearchInput
from src.data_sources.telegram_scraper.client import TelegramScraperClient
from src.tools.crypto_news_search import CryptoNewsSearchTool


@pytest.mark.unit
class TestCryptoNewsSearchTool:
    @pytest.fixture
    def mock_telegram_scraper_client(self):
        client = MagicMock(spec=TelegramScraperClient)
        client.search_messages = AsyncMock(
            return_value=(
                [
                    {
                        "title": "Channel A: BTC bullish",
                        "url": "https://t.me/channel_a/123",
                        "snippet": "BTC looks bullish",
                        "source": "Telegram - Channel A",
                        "published_at": "2025-01-02T03:04:05Z",
                        "relevance_score": 1.23,
                        "telegram_meta": {"channel_username": "channel_a", "message_id": "123"},
                    },
                    {
                        "title": "Channel B: ETH update",
                        "url": "https://t.me/channel_b/456",
                        "snippet": "ETH upgrade soon",
                        "source": "Telegram - Channel B",
                        "published_at": "2025-01-02T02:00:00Z",
                        "relevance_score": 0.9,
                    },
                ],
                SourceMeta(
                    provider="telegram_scraper",
                    endpoint="/telegram_messages/_search",
                    as_of_utc="2025-01-02T03:04:06Z",
                    ttl_seconds=60,
                ),
            )
        )
        return client

    @pytest.mark.asyncio
    async def test_execute_without_client_returns_warning(self):
        tool = CryptoNewsSearchTool(telegram_scraper_client=None)
        result = await tool.execute(CryptoNewsSearchInput(query="btc", limit=5))

        assert result.total_results == 0
        assert result.source_meta == []
        assert any("Telegram scraper 未初始化" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_execute_with_client_returns_results(self, mock_telegram_scraper_client):
        tool = CryptoNewsSearchTool(telegram_scraper_client=mock_telegram_scraper_client)
        result = await tool.execute({"query": "btc", "limit": 2, "sort_by": "score"})

        assert result.query == "btc"
        assert result.total_results == 2
        assert len(result.results) == 2
        assert result.results[0].source.startswith("Telegram -")
        assert len(result.source_meta) == 1

        mock_telegram_scraper_client.search_messages.assert_awaited_once()
        _, kwargs = mock_telegram_scraper_client.search_messages.call_args
        assert kwargs["keyword"] == "btc"
        assert kwargs["symbol"] is None
        assert kwargs["limit"] == 2
        assert kwargs["sort_by"] == "score"
        assert kwargs["start_time"] is None

    @pytest.mark.asyncio
    async def test_time_range_is_converted_to_start_time(self, mock_telegram_scraper_client):
        tool = CryptoNewsSearchTool(telegram_scraper_client=mock_telegram_scraper_client)
        tool._parse_time_range = MagicMock(return_value=datetime(2025, 1, 2, 3, 4, 5))

        await tool.execute({"query": "btc", "time_range": "24h", "limit": 1})

        _, kwargs = mock_telegram_scraper_client.search_messages.call_args
        assert kwargs["start_time"] == "2025-01-02T03:04:05Z"

    @pytest.mark.asyncio
    async def test_no_query_or_symbol_searches_latest(self, mock_telegram_scraper_client):
        tool = CryptoNewsSearchTool(telegram_scraper_client=mock_telegram_scraper_client)

        result = await tool.execute({"limit": 1})
        assert any("返回最新消息" in w for w in result.warnings)

        _, kwargs = mock_telegram_scraper_client.search_messages.call_args
        assert kwargs["keyword"] is None
        assert kwargs["symbol"] is None


@pytest.mark.unit
class TestCryptoNewsSearchInput:
    def test_symbol_is_uppercased(self):
        assert CryptoNewsSearchInput(symbol="btc").symbol == "BTC"

    def test_sort_by_validation(self):
        with pytest.raises(ValueError, match="sort_by must be 'timestamp' or 'score'"):
            CryptoNewsSearchInput(sort_by="invalid")

