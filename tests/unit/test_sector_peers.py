"""
sector_peers 工具单元测试

测试板块竞品对比功能
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.models import (
    SectorPeersInput,
    SectorPeersOutput,
    SectorPeersSortBy,
    SourceMeta,
)
from src.tools.market.sector_peers import SectorPeersTool, SECTOR_MAPPING


class TestSectorPeersTool:
    """SectorPeersTool 测试"""

    @pytest.fixture
    def mock_coingecko_client(self):
        """Mock CoinGecko客户端"""
        client = MagicMock()
        return client

    @pytest.fixture
    def mock_defillama_client(self):
        """Mock DefiLlama客户端"""
        client = MagicMock()
        return client

    @pytest.fixture
    def tool(self, mock_coingecko_client, mock_defillama_client):
        """创建工具实例"""
        return SectorPeersTool(
            coingecko_client=mock_coingecko_client,
            defillama_client=mock_defillama_client,
        )

    @pytest.fixture
    def sample_coin_data(self):
        """示例代币数据"""
        return {
            "id": "aave",
            "symbol": "aave",
            "name": "Aave",
            "categories": ["decentralized-finance-defi", "lending-borrowing"],
            "market_data": {
                "current_price": {"usd": 150.0},
                "market_cap": {"usd": 2000000000},
                "total_volume": {"usd": 100000000},
                "market_cap_rank": 50,
                "price_change_percentage_24h": 2.5,
                "price_change_percentage_7d": -1.2,
            },
            "community_data": {
                "twitter_followers": 500000,
            },
        }

    @pytest.fixture
    def sample_category_coins(self):
        """示例分类代币列表"""
        return [
            {
                "id": "compound-governance-token",
                "symbol": "comp",
                "name": "Compound",
                "market_data": {
                    "current_price": {"usd": 50.0},
                    "market_cap": {"usd": 500000000},
                    "total_volume": {"usd": 20000000},
                    "market_cap_rank": 100,
                    "price_change_percentage_7d": 3.5,
                },
            },
            {
                "id": "maker",
                "symbol": "mkr",
                "name": "Maker",
                "market_data": {
                    "current_price": {"usd": 1500.0},
                    "market_cap": {"usd": 1500000000},
                    "total_volume": {"usd": 50000000},
                    "market_cap_rank": 60,
                    "price_change_percentage_7d": -0.5,
                },
            },
        ]

    @pytest.mark.asyncio
    async def test_execute_basic(self, tool, mock_coingecko_client, sample_coin_data, sample_category_coins):
        """测试基本执行"""
        # Setup mocks
        mock_coingecko_client.get_coin_data = AsyncMock(return_value=(sample_coin_data, SourceMeta(
            provider="coingecko",
            endpoint="/coins/aave",
            as_of_utc=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=300,
        )))
        
        mock_coingecko_client.get_category_detail = AsyncMock(return_value=(sample_category_coins, SourceMeta(
            provider="coingecko",
            endpoint="/coins/categories/decentralized-finance-defi",
            as_of_utc=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=300,
        )))
        
        params = SectorPeersInput(symbol="AAVE", limit=5)
        result = await tool.execute(params)
        
        # 验证返回类型
        assert isinstance(result, SectorPeersOutput)
        assert result.target_symbol == "AAVE"
        assert "DeFi" in result.sector
        
        # 验证竞品列表
        assert len(result.peers) > 0
        
        # 目标代币应该在列表中
        target_peer = next((p for p in result.peers if p.is_target), None)
        assert target_peer is not None
        assert target_peer.symbol == "AAVE"

    @pytest.mark.asyncio
    async def test_execute_with_tvl(self, tool, mock_coingecko_client, mock_defillama_client, sample_coin_data, sample_category_coins):
        """测试包含TVL数据"""
        mock_coingecko_client.get_coin_data = AsyncMock(return_value=(sample_coin_data, SourceMeta(
            provider="coingecko",
            endpoint="/coins/aave",
            as_of_utc=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=300,
        )))
        
        mock_coingecko_client.get_category_detail = AsyncMock(return_value=(sample_category_coins, SourceMeta(
            provider="coingecko",
            endpoint="/coins/categories/decentralized-finance-defi",
            as_of_utc=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=300,
        )))
        
        # Mock TVL data
        mock_defillama_client.get_protocol_tvl = AsyncMock(return_value=(
            {"tvl": 5000000000},
            SourceMeta(
                provider="defillama",
                endpoint="/protocol/aave",
                as_of_utc=datetime.utcnow().isoformat() + "Z",
                ttl_seconds=300,
            )
        ))
        
        params = SectorPeersInput(
            symbol="AAVE",
            limit=5,
            include_metrics=["market", "tvl"],
        )
        result = await tool.execute(params)
        
        assert isinstance(result, SectorPeersOutput)

    @pytest.mark.asyncio
    async def test_sort_by_market_cap(self, tool, mock_coingecko_client, sample_coin_data, sample_category_coins):
        """测试按市值排序"""
        mock_coingecko_client.get_coin_data = AsyncMock(return_value=(sample_coin_data, SourceMeta(
            provider="coingecko",
            endpoint="/coins/aave",
            as_of_utc=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=300,
        )))
        
        mock_coingecko_client.get_category_detail = AsyncMock(return_value=(sample_category_coins, SourceMeta(
            provider="coingecko",
            endpoint="/coins/categories/decentralized-finance-defi",
            as_of_utc=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=300,
        )))
        
        params = SectorPeersInput(
            symbol="AAVE",
            limit=10,
            sort_by=SectorPeersSortBy.MARKET_CAP,
        )
        result = await tool.execute(params)
        
        # 验证排序（市值从高到低）
        market_caps = [p.market_cap for p in result.peers if p.market_cap]
        if len(market_caps) > 1:
            for i in range(len(market_caps) - 1):
                assert market_caps[i] >= market_caps[i + 1]

    @pytest.mark.asyncio
    async def test_sector_stats(self, tool, mock_coingecko_client, sample_coin_data, sample_category_coins):
        """测试板块统计"""
        mock_coingecko_client.get_coin_data = AsyncMock(return_value=(sample_coin_data, SourceMeta(
            provider="coingecko",
            endpoint="/coins/aave",
            as_of_utc=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=300,
        )))
        
        mock_coingecko_client.get_category_detail = AsyncMock(return_value=(sample_category_coins, SourceMeta(
            provider="coingecko",
            endpoint="/coins/categories/decentralized-finance-defi",
            as_of_utc=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=300,
        )))
        
        params = SectorPeersInput(symbol="AAVE", limit=5)
        result = await tool.execute(params)
        
        # 验证板块统计存在
        assert result.sector_stats is not None

    @pytest.mark.asyncio
    async def test_unknown_symbol(self, tool, mock_coingecko_client):
        """测试未知符号"""
        mock_coingecko_client.get_coin_data = AsyncMock(return_value=(None, SourceMeta(
            provider="coingecko",
            endpoint="/coins/unknown",
            as_of_utc=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=300,
            degraded=True,
        )))
        
        params = SectorPeersInput(symbol="UNKNOWNTOKEN", limit=5)
        result = await tool.execute(params)
        
        # 应该返回警告
        assert len(result.warnings) > 0

    def test_input_validation(self):
        """测试输入验证"""
        # 正常输入
        params = SectorPeersInput(symbol="aave", limit=10)
        # symbol应该被转为大写
        assert params.symbol == "AAVE"
        
        # limit边界测试
        with pytest.raises(Exception):
            SectorPeersInput(symbol="AAVE", limit=25)  # 超过最大值

    def test_sector_mapping(self):
        """测试板块映射"""
        assert SECTOR_MAPPING["decentralized-finance-defi"] == "DeFi"
        assert SECTOR_MAPPING["lending-borrowing"] == "DeFi - Lending"
        assert SECTOR_MAPPING["layer-1"] == "Layer 1"
