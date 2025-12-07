"""
CoinGeckoClient 单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.models import SourceMeta
from src.data_sources.coingecko import CoinGeckoClient


class TestCoinGeckoClient:
    """CoinGeckoClient测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return CoinGeckoClient(api_key="test_api_key")

    @pytest.fixture
    def client_without_key(self):
        """创建无API密钥的客户端（免费版）"""
        return CoinGeckoClient()

    def test_init_with_api_key(self, client):
        """测试使用API密钥初始化"""
        assert client.api_key == "test_api_key"
        assert client.name == "coingecko"
        assert client.base_url == "https://api.coingecko.com/api/v3"
        assert client.requires_api_key is False

    def test_init_without_api_key(self, client_without_key):
        """测试免费版初始化"""
        assert client_without_key.api_key is None

    def test_get_headers_with_key(self, client):
        """测试带API密钥的请求头"""
        headers = client._get_headers()
        assert headers["x-cg-pro-api-key"] == "test_api_key"
        assert headers["accept"] == "application/json"

    def test_get_headers_without_key(self, client_without_key):
        """测试无API密钥的请求头"""
        headers = client_without_key._get_headers()
        assert "x-cg-pro-api-key" not in headers

    def test_transform_basic(self, client):
        """测试基础信息转换"""
        raw_data = {
            "id": "bitcoin",
            "symbol": "btc",
            "name": "Bitcoin",
            "description": {"en": "Bitcoin is the first decentralized cryptocurrency."},
            "links": {
                "homepage": ["https://bitcoin.org", "https://bitcoin.com"],
                "blockchain_site": ["https://blockstream.info", "https://btc.com", "https://blockchain.com", "https://other.com"],
            },
            "contract_address": None,
            "asset_platform_id": None,
        }

        result = client._transform_basic(raw_data)

        assert result["id"] == "bitcoin"
        assert result["symbol"] == "BTC"
        assert result["name"] == "Bitcoin"
        assert len(result["homepage"]) == 1
        assert len(result["blockchain_site"]) == 3

    def test_transform_basic_long_description(self, client):
        """测试长描述截断"""
        raw_data = {
            "id": "test",
            "symbol": "test",
            "name": "Test",
            "description": {"en": "A" * 1000},
            "links": {},
        }

        result = client._transform_basic(raw_data)
        assert len(result["description"]) == 500

    def test_transform_market(self, client):
        """测试市场数据转换"""
        raw_data = {
            "market_data": {
                "current_price": {"usd": 45000},
                "market_cap": {"usd": 850000000000},
                "fully_diluted_valuation": {"usd": 945000000000},
                "total_volume": {"usd": 25000000000},
                "high_24h": {"usd": 46000},
                "low_24h": {"usd": 44000},
                "price_change_24h": 1000,
                "price_change_percentage_24h": 2.27,
                "market_cap_rank": 1,
                "ath": {"usd": 69000},
                "atl": {"usd": 67},
            }
        }

        result = client._transform_market(raw_data)

        assert result["price"] == 45000
        assert result["market_cap"] == 850000000000
        assert result["market_cap_rank"] == 1
        assert result["high_24h"] == 46000
        assert result["low_24h"] == 44000
        assert result["ath"] == 69000
        assert result["atl"] == 67

    def test_transform_supply(self, client):
        """测试供应信息转换"""
        raw_data = {
            "market_data": {
                "circulating_supply": 19000000,
                "total_supply": 21000000,
                "max_supply": 21000000,
            }
        }

        result = client._transform_supply(raw_data)

        assert result["circulating_supply"] == 19000000
        assert result["total_supply"] == 21000000
        assert result["max_supply"] == 21000000
        # 流通占比: (19000000 / 21000000) * 100 ≈ 90.48%
        assert result["circulating_percent"] == pytest.approx(90.48, rel=0.01)

    def test_transform_supply_no_max(self, client):
        """测试无最大供应量的供应信息"""
        raw_data = {
            "market_data": {
                "circulating_supply": 120000000,
                "total_supply": 120000000,
                "max_supply": None,
            }
        }

        result = client._transform_supply(raw_data)

        assert result["circulating_supply"] == 120000000
        assert result["circulating_percent"] is None

    def test_transform_social(self, client):
        """测试社交信息转换"""
        raw_data = {
            "community_data": {
                "twitter_followers": 5000000,
                "reddit_subscribers": 4000000,
                "telegram_channel_user_count": 100000,
            }
        }

        result = client._transform_social(raw_data)

        assert result["twitter_followers"] == 5000000
        assert result["reddit_subscribers"] == 4000000
        assert result["telegram_members"] == 100000
        assert result["discord_members"] is None

    def test_transform_sector(self, client):
        """测试板块信息转换"""
        raw_data = {
            "categories": ["Cryptocurrency", "Layer 1 (L1)", "Smart Contract Platform"]
        }

        result = client._transform_sector(raw_data)

        assert len(result["categories"]) == 3
        assert result["primary_category"] == "Cryptocurrency"

    def test_transform_sector_empty(self, client):
        """测试空板块信息"""
        raw_data = {"categories": []}

        result = client._transform_sector(raw_data)

        assert result["categories"] == []
        assert result["primary_category"] is None

    def test_transform_unknown_type(self, client):
        """测试未知数据类型"""
        raw_data = {"test": "data"}
        result = client.transform(raw_data, "unknown")
        assert result == raw_data

    @pytest.mark.asyncio
    async def test_symbol_to_id_common_mapping(self, client):
        """测试常见币种映射"""
        assert await client._symbol_to_id("BTC") == "bitcoin"
        assert await client._symbol_to_id("ETH") == "ethereum"
        assert await client._symbol_to_id("SOL") == "solana"
        assert await client._symbol_to_id("USDT") == "tether"
        assert await client._symbol_to_id("UNI") == "uniswap"
        assert await client._symbol_to_id("ARB") == "arbitrum"

    @pytest.mark.asyncio
    async def test_symbol_to_id_case_insensitive(self, client):
        """测试symbol大小写不敏感"""
        assert await client._symbol_to_id("btc") == "bitcoin"
        assert await client._symbol_to_id("Eth") == "ethereum"

    @pytest.mark.asyncio
    async def test_symbol_to_id_search_api(self, client):
        """测试通过search API查找币种"""
        mock_response = {
            "coins": [
                {"id": "test-coin", "name": "Test Coin", "symbol": "TEST"}
            ]
        }

        with patch.object(client, "fetch_raw", return_value=mock_response):
            result = await client._symbol_to_id("TEST")
            assert result == "test-coin"

    @pytest.mark.asyncio
    async def test_symbol_to_id_not_found(self, client):
        """测试找不到币种"""
        mock_response = {"coins": []}

        with patch.object(client, "fetch_raw", return_value=mock_response):
            with pytest.raises(ValueError, match="not found"):
                await client._symbol_to_id("UNKNOWN")

    @pytest.mark.asyncio
    async def test_symbol_to_id_api_error_fallback(self, client):
        """测试API错误时降级"""
        with patch.object(client, "fetch_raw", side_effect=Exception("API Error")):
            result = await client._symbol_to_id("TEST")
            # 降级到小写symbol
            assert result == "test"

    @pytest.mark.asyncio
    async def test_get_coin_data(self, client):
        """测试获取代币完整数据"""
        mock_coin_data = {
            "id": "bitcoin",
            "symbol": "btc",
            "name": "Bitcoin",
            "market_data": {
                "current_price": {"usd": 45000}
            }
        }

        with patch.object(client, "_symbol_to_id", return_value="bitcoin"):
            with patch.object(client, "fetch_raw", return_value=mock_coin_data):
                result = await client.get_coin_data("BTC")

                assert result["id"] == "bitcoin"
                assert result["symbol"] == "btc"

    @pytest.mark.asyncio
    async def test_get_categories(self, client):
        """测试获取所有分类"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ([], mock_meta)

            await client.get_categories()

            mock_fetch.assert_called_once_with(
                endpoint="/coins/categories",
                params={"order": "market_cap_desc"},
                data_type="categories",
                ttl_seconds=3600,
            )

    @pytest.mark.asyncio
    async def test_get_category_detail(self, client):
        """测试获取特定分类详情"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_category_detail("decentralized-finance-defi")

            mock_fetch.assert_called_once_with(
                endpoint="/coins/categories/decentralized-finance-defi",
                params={},
                data_type="category_detail",
                ttl_seconds=1800,
            )

    def test_transform_market_empty(self, client):
        """测试空市场数据"""
        raw_data = {"market_data": {}}

        result = client._transform_market(raw_data)

        assert result["price"] is None
        assert result["market_cap"] is None

    def test_transform_social_empty(self, client):
        """测试空社交数据"""
        raw_data = {"community_data": {}}

        result = client._transform_social(raw_data)

        assert result["twitter_followers"] is None
        assert result["reddit_subscribers"] is None

    def test_transform_basic_empty_links(self, client):
        """测试空链接数据"""
        raw_data = {
            "id": "test",
            "symbol": "test",
            "name": "Test",
            "links": {},
        }

        result = client._transform_basic(raw_data)

        assert result["homepage"] == []
        assert result["blockchain_site"] == []

    def test_transform_basic_no_description(self, client):
        """测试无描述数据"""
        raw_data = {
            "id": "test",
            "symbol": "test",
            "name": "Test",
            "description": None,
            "links": {},
        }

        result = client._transform_basic(raw_data)

        assert result["description"] is None
