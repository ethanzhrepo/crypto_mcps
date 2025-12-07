"""
SearchClient 搜索客户端单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.models import SourceMeta
from src.data_sources.search import SearchClient


class TestSearchClient:
    """SearchClient测试"""

    @pytest.fixture
    def client_with_all_keys(self):
        """创建包含所有API密钥的客户端"""
        return SearchClient(
            brave_api_key="test_brave_key",
            google_api_key="test_google_key",
            google_cse_id="test_cse_id",
            bing_api_key="test_bing_key",
            serpapi_key="test_serpapi_key",
            kaito_api_key="test_kaito_key",
        )

    @pytest.fixture
    def client_without_keys(self):
        """创建不包含API密钥的客户端（仅DuckDuckGo）"""
        return SearchClient()

    @pytest.mark.asyncio
    async def test_auto_provider_selection_with_google(self, client_with_all_keys):
        """测试有Google key时自动选择Google"""
        with patch.object(client_with_all_keys, "_search_google") as mock_google:
            mock_google.return_value = ([], MagicMock(spec=SourceMeta))

            await client_with_all_keys.search_web("test query", provider="auto")

            mock_google.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_provider_selection_fallback_to_duckduckgo(self, client_without_keys):
        """测试无API key时fallback到DuckDuckGo"""
        with patch.object(client_without_keys, "_search_duckduckgo") as mock_ddg:
            mock_ddg.return_value = ([], MagicMock(spec=SourceMeta))

            await client_without_keys.search_web("test query", provider="auto")

            mock_ddg.assert_called_once()

    @pytest.mark.asyncio
    async def test_explicit_provider_google(self, client_with_all_keys):
        """测试显式指定Google提供商"""
        with patch.object(client_with_all_keys, "_search_google") as mock_google:
            mock_google.return_value = ([], MagicMock(spec=SourceMeta))

            await client_with_all_keys.search_web("test query", provider="google")

            mock_google.assert_called_once_with("test query", 10)

    @pytest.mark.asyncio
    async def test_explicit_provider_bing(self, client_with_all_keys):
        """测试显式指定Bing提供商"""
        with patch.object(client_with_all_keys, "_search_bing") as mock_bing:
            mock_bing.return_value = ([], MagicMock(spec=SourceMeta))

            await client_with_all_keys.search_web("test query", provider="bing")

            mock_bing.assert_called_once_with("test query", 10)

    @pytest.mark.asyncio
    async def test_google_requires_credentials(self):
        """测试Google搜索需要API key和CSE ID"""
        client = SearchClient()

        with pytest.raises(ValueError, match="Google Search requires"):
            await client._search_google("test query", 10)

    @pytest.mark.asyncio
    async def test_bing_requires_api_key(self):
        """测试Bing搜索需要API key"""
        client = SearchClient()

        with pytest.raises(ValueError, match="Bing Search requires"):
            await client._search_bing("test query", 10)

    @pytest.mark.asyncio
    async def test_serpapi_requires_api_key(self):
        """测试SerpAPI需要API key"""
        client = SearchClient()

        with pytest.raises(ValueError, match="SerpAPI requires"):
            await client._search_serpapi("test query", 10)

    @pytest.mark.asyncio
    async def test_kaito_requires_api_key(self):
        """测试Kaito需要API key"""
        client = SearchClient()

        with pytest.raises(ValueError, match="Kaito requires"):
            await client._search_kaito("test query", 10)

    def test_transform_duckduckgo(self, client_without_keys):
        """测试DuckDuckGo结果转换"""
        raw_data = {
            "Abstract": "Bitcoin is a cryptocurrency",
            "AbstractURL": "https://bitcoin.org",
            "Heading": "Bitcoin",
            "AbstractSource": "Wikipedia",
            "RelatedTopics": [
                {
                    "Text": "Bitcoin wallet",
                    "FirstURL": "https://bitcoin.org/en/choose-your-wallet"
                }
            ]
        }

        results = client_without_keys._transform_duckduckgo(raw_data)

        assert len(results) == 2  # Abstract + 1 related topic
        assert results[0]["title"] == "Bitcoin"
        assert results[0]["snippet"] == "Bitcoin is a cryptocurrency"
        assert results[0]["relevance_score"] == 1.0

    def test_transform_brave(self, client_without_keys):
        """测试Brave结果转换"""
        raw_data = {
            "web": {
                "results": [
                    {
                        "title": "Bitcoin - Peer-to-Peer Electronic Cash",
                        "url": "https://bitcoin.org",
                        "description": "Bitcoin is an innovative payment network"
                    }
                ]
            }
        }

        results = client_without_keys._transform_brave(raw_data)

        assert len(results) == 1
        assert results[0]["title"] == "Bitcoin - Peer-to-Peer Electronic Cash"
        assert results[0]["source"] == "Brave Search"

    def test_transform_google(self, client_without_keys):
        """测试Google结果转换"""
        raw_data = {
            "items": [
                {
                    "title": "Bitcoin.org",
                    "link": "https://bitcoin.org",
                    "snippet": "Bitcoin is an innovative payment network"
                }
            ]
        }

        results = client_without_keys._transform_google(raw_data)

        assert len(results) == 1
        assert results[0]["title"] == "Bitcoin.org"
        assert results[0]["source"] == "Google"

    def test_transform_bing(self, client_without_keys):
        """测试Bing结果转换"""
        raw_data = {
            "webPages": {
                "value": [
                    {
                        "name": "Bitcoin.org",
                        "url": "https://bitcoin.org",
                        "snippet": "Bitcoin is an innovative payment network"
                    }
                ]
            }
        }

        results = client_without_keys._transform_bing(raw_data)

        assert len(results) == 1
        assert results[0]["title"] == "Bitcoin.org"
        assert results[0]["source"] == "Bing"

    def test_transform_serpapi(self, client_without_keys):
        """测试SerpAPI结果转换"""
        raw_data = {
            "organic_results": [
                {
                    "title": "Bitcoin.org",
                    "link": "https://bitcoin.org",
                    "snippet": "Bitcoin is an innovative payment network",
                    "position": 1,
                    "source": "Google"
                }
            ]
        }

        results = client_without_keys._transform_serpapi(raw_data)

        assert len(results) == 1
        assert results[0]["title"] == "Bitcoin.org"
        assert "SerpAPI" in results[0]["source"]
        assert results[0]["relevance_score"] == 1

    def test_transform_kaito_results_structure(self, client_without_keys):
        """测试Kaito结果转换（results结构）"""
        raw_data = {
            "results": [
                {
                    "title": "Bitcoin Price Analysis",
                    "url": "https://example.com/btc",
                    "description": "BTC price analysis",
                    "category": "Market Analysis",
                    "score": 0.95
                }
            ]
        }

        results = client_without_keys._transform_kaito(raw_data)

        assert len(results) == 1
        assert results[0]["title"] == "Bitcoin Price Analysis"
        assert "Kaito" in results[0]["source"]
        assert results[0]["relevance_score"] == 0.95

    def test_transform_kaito_data_structure(self, client_without_keys):
        """测试Kaito结果转换（data备用结构）"""
        raw_data = {
            "data": [
                {
                    "title": "Ethereum DeFi Report",
                    "link": "https://example.com/eth",
                    "summary": "ETH DeFi ecosystem overview"
                }
            ]
        }

        results = client_without_keys._transform_kaito(raw_data)

        assert len(results) == 1
        assert results[0]["title"] == "Ethereum DeFi Report"
        assert results[0]["source"] == "Kaito"

    def test_transform_empty_results(self, client_without_keys):
        """测试空结果转换"""
        assert client_without_keys._transform_duckduckgo({}) == []
        assert client_without_keys._transform_brave({}) == []
        assert client_without_keys._transform_google({}) == []
        assert client_without_keys._transform_bing({}) == []
        assert client_without_keys._transform_serpapi({}) == []
        assert client_without_keys._transform_kaito({}) == []
