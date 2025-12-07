"""
web_research_search 工具单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.core.models import (
    WebResearchInput,
    SearchResult,
    SourceMeta,
)
from src.tools.web_research import WebResearchTool
from src.data_sources.search import SearchClient


class TestWebResearchTool:
    """web_research_search工具测试"""

    @pytest.fixture
    def mock_search_client(self):
        """模拟SearchClient"""
        client = MagicMock(spec=SearchClient)
        client.google_api_key = "test_key"
        client.google_cse_id = "test_cse"
        client.brave_api_key = None
        client.bing_api_key = "test_bing_key"
        client.serpapi_key = None
        client.kaito_api_key = None

        # 模拟search_web响应
        client.search_web = AsyncMock(return_value=(
            [
                {
                    "title": "Bitcoin Documentation",
                    "url": "https://bitcoin.org/en/developer-documentation",
                    "snippet": "Bitcoin uses peer-to-peer technology",
                    "source": "Google",
                    "relevance_score": None,
                }
            ],
            SourceMeta(
                provider="google",
                endpoint="/customsearch/v1",
                as_of_utc="2025-11-18T12:00:00Z",
                ttl_seconds=3600,
            )
        ))

        return client

    @pytest.fixture
    def tool(self, mock_search_client):
        """创建工具实例"""
        return WebResearchTool(search_client=mock_search_client)

    @pytest.mark.asyncio
    async def test_web_scope_search(self, tool):
        """测试web搜索范围"""
        params = WebResearchInput(
            query="bitcoin blockchain",
            scope="web",
            limit=10
        )

        result = await tool.execute(params)

        assert result.query == "bitcoin blockchain"
        assert result.total_results == 1
        assert len(result.results) == 1
        assert result.results[0].title == "Bitcoin Documentation"
        assert len(result.source_meta) == 1

    @pytest.mark.asyncio
    async def test_web_scope_with_provider(self, tool):
        """测试指定搜索提供商"""
        params = WebResearchInput(
            query="ethereum smart contracts",
            scope="web",
            providers=["google"],
            limit=10
        )

        result = await tool.execute(params)

        # 验证调用了search_web且provider设置正确
        tool.search_client.search_web.assert_called_once()
        call_args = tool.search_client.search_web.call_args
        assert call_args[1]["provider"] == "google"

    @pytest.mark.asyncio
    async def test_academic_scope_semantic_scholar(self, tool):
        """测试学术搜索（Semantic Scholar）"""
        with patch.object(tool, "_search_semantic_scholar") as mock_ss:
            mock_ss.return_value = [
                {
                    "title": "Bitcoin: A Peer-to-Peer Electronic Cash System",
                    "url": "https://www.semanticscholar.org/paper/abc123",
                    "snippet": "Abstract: A purely peer-to-peer... (Year: 2008, Authors: Satoshi Nakamoto)",
                    "source": "Semantic Scholar",
                    "relevance_score": None,
                }
            ]

            with patch.object(tool, "_search_arxiv") as mock_arxiv:
                mock_arxiv.return_value = []

                params = WebResearchInput(
                    query="blockchain consensus",
                    scope="academic",
                    limit=10
                )

                result = await tool.execute(params)

                assert result.total_results == 1
                assert "Semantic Scholar" in result.results[0].source
                mock_ss.assert_called_once()

    @pytest.mark.asyncio
    async def test_academic_scope_arxiv(self, tool):
        """测试学术搜索（Arxiv）"""
        with patch.object(tool, "_search_semantic_scholar") as mock_ss:
            mock_ss.return_value = []

            with patch.object(tool, "_search_arxiv") as mock_arxiv:
                mock_arxiv.return_value = [
                    {
                        "title": "Deep Learning for Blockchain",
                        "url": "http://arxiv.org/abs/2101.12345",
                        "snippet": "We present a novel approach... (Published: 2021-01-15, Authors: John Doe, Jane Smith)",
                        "source": "Arxiv",
                        "relevance_score": None,
                    }
                ]

                params = WebResearchInput(
                    query="blockchain AI",
                    scope="academic",
                    limit=10
                )

                result = await tool.execute(params)

                assert result.total_results == 1
                assert result.results[0].source == "Arxiv"
                mock_arxiv.assert_called_once()

    @pytest.mark.asyncio
    async def test_academic_scope_fallback(self, tool):
        """测试学术搜索fallback到Google Scholar"""
        with patch.object(tool, "_search_semantic_scholar") as mock_ss:
            mock_ss.return_value = []

            with patch.object(tool, "_search_arxiv") as mock_arxiv:
                mock_arxiv.return_value = []

                params = WebResearchInput(
                    query="quantum computing",
                    scope="academic",
                    limit=10
                )

                result = await tool.execute(params)

                # 应该调用search_web作为fallback
                tool.search_client.search_web.assert_called_once()
                call_args = tool.search_client.search_web.call_args
                assert "scholar.google.com" in call_args[1]["query"]

    @pytest.mark.asyncio
    async def test_news_scope_bing_news(self, tool):
        """测试新闻搜索（Bing News API）"""
        tool.search_client.bing_api_key = "test_bing_key"

        with patch.object(tool, "_search_bing_news") as mock_bing_news:
            mock_bing_news.return_value = [
                SearchResult(
                    title="Bitcoin hits new high",
                    url="https://reuters.com/article/123",
                    snippet="Bitcoin reached $100,000 today",
                    source="Bing News - Reuters",
                    relevance_score=None,
                )
            ]

            params = WebResearchInput(
                query="bitcoin price",
                scope="news",
                limit=10
            )

            result = await tool.execute(params)

            assert result.total_results == 1
            assert "Reuters" in result.results[0].source
            mock_bing_news.assert_called_once()

    @pytest.mark.asyncio
    async def test_news_scope_fallback(self, tool):
        """测试新闻搜索fallback到site过滤"""
        tool.search_client.bing_api_key = None

        params = WebResearchInput(
            query="ethereum upgrade",
            scope="news",
            limit=10
        )

        result = await tool.execute(params)

        # 应该调用search_web with site filter
        tool.search_client.search_web.assert_called_once()
        call_args = tool.search_client.search_web.call_args
        query = call_args[1]["query"]
        assert "site:reuters.com" in query or "site:bloomberg.com" in query

    @pytest.mark.asyncio
    async def test_unknown_scope(self, tool):
        """测试未知搜索范围"""
        params = WebResearchInput(
            query="test",
            scope="unknown_scope",
            limit=10
        )

        result = await tool.execute(params)

        assert result.total_results == 0
        assert len(result.warnings) == 1
        assert "Unknown search scope" in result.warnings[0]

    @pytest.mark.asyncio
    async def test_time_range_filter(self, tool):
        """测试时间范围过滤"""
        params = WebResearchInput(
            query="bitcoin news",
            scope="web",
            time_range="day",
            limit=10
        )

        result = await tool.execute(params)

        # 时间过滤应该被调用（目前是placeholder）
        assert result.total_results >= 0

    @pytest.mark.asyncio
    async def test_provider_priority(self, tool):
        """测试provider优先级"""
        tool.search_client.google_api_key = "test_google"
        tool.search_client.brave_api_key = "test_brave"

        params = WebResearchInput(
            query="test",
            scope="web",
            providers=["brave", "google"],  # brave优先
            limit=10
        )

        result = await tool.execute(params)

        call_args = tool.search_client.search_web.call_args
        assert call_args[1]["provider"] == "brave"

    def test_filter_by_time_range(self, tool):
        """测试时间过滤方法"""
        results = [
            {"title": "Result 1", "url": "https://example.com/1"},
            {"title": "Result 2", "url": "https://example.com/2"},
        ]

        # 目前_filter_by_time_range是placeholder，应该返回所有结果
        filtered = tool._filter_by_time_range(results, "week")

        assert len(filtered) == 2


class TestSemanticScholarIntegration:
    """Semantic Scholar集成测试"""

    @pytest.mark.asyncio
    async def test_search_semantic_scholar_success(self):
        """测试成功调用Semantic Scholar API"""
        tool = WebResearchTool()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "paperId": "abc123",
                    "title": "Test Paper",
                    "abstract": "This is a test abstract",
                    "url": "https://www.semanticscholar.org/paper/abc123",
                    "year": 2023,
                    "authors": [
                        {"name": "John Doe"},
                        {"name": "Jane Smith"}
                    ]
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            results = await tool._search_semantic_scholar("blockchain", 10)

            assert len(results) == 1
            assert results[0]["title"] == "Test Paper"
            assert results[0]["source"] == "Semantic Scholar"
            assert "John Doe" in results[0]["snippet"]

    @pytest.mark.asyncio
    async def test_search_semantic_scholar_empty_results(self):
        """测试Semantic Scholar返回空结果"""
        tool = WebResearchTool()

        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            results = await tool._search_semantic_scholar("nonexistent", 10)

            assert len(results) == 0


class TestArxivIntegration:
    """Arxiv集成测试"""

    @pytest.mark.asyncio
    async def test_search_arxiv_success(self):
        """测试成功调用Arxiv API"""
        tool = WebResearchTool()

        xml_response = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <entry>
                <id>http://arxiv.org/abs/2101.12345</id>
                <title>Test Arxiv Paper</title>
                <summary>This is a test summary for arxiv paper</summary>
                <published>2021-01-15T00:00:00Z</published>
                <author><name>Alice</name></author>
                <author><name>Bob</name></author>
            </entry>
        </feed>"""

        mock_response = MagicMock()
        mock_response.text = xml_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            results = await tool._search_arxiv("quantum", 10)

            assert len(results) == 1
            assert results[0]["title"] == "Test Arxiv Paper"
            assert results[0]["source"] == "Arxiv"
            assert "Alice" in results[0]["snippet"]
            assert "2021-01-15" in results[0]["snippet"]

    @pytest.mark.asyncio
    async def test_search_arxiv_empty_results(self):
        """测试Arxiv返回空结果"""
        tool = WebResearchTool()

        xml_response = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
        </feed>"""

        mock_response = MagicMock()
        mock_response.text = xml_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            results = await tool._search_arxiv("nonexistent", 10)

            assert len(results) == 0


class TestBingNewsIntegration:
    """Bing News集成测试"""

    @pytest.mark.asyncio
    async def test_search_bing_news_success(self):
        """测试成功调用Bing News API"""
        search_client = MagicMock(spec=SearchClient)
        search_client.bing_api_key = "test_key"

        tool = WebResearchTool(search_client=search_client)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "value": [
                {
                    "name": "Bitcoin Surges to New High",
                    "url": "https://reuters.com/bitcoin-high",
                    "description": "Bitcoin reached $100k today",
                    "provider": [{"name": "Reuters"}]
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            results = await tool._search_bing_news("bitcoin", 10)

            assert len(results) == 1
            assert results[0].title == "Bitcoin Surges to New High"
            assert "Reuters" in results[0].source

    @pytest.mark.asyncio
    async def test_search_bing_news_requires_api_key(self):
        """测试Bing News需要API key"""
        search_client = MagicMock(spec=SearchClient)
        search_client.bing_api_key = None

        tool = WebResearchTool(search_client=search_client)

        with pytest.raises(ValueError, match="Bing News requires API key"):
            await tool._search_bing_news("test", 10)
