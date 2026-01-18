"""
DefiLlamaClient 单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.models import SourceMeta
from src.data_sources.defillama import DefiLlamaClient


class TestDefiLlamaClient:
    """DefiLlamaClient测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return DefiLlamaClient()

    def test_init(self, client):
        """测试初始化"""
        assert client.base_url == "https://api.llama.fi"

    @pytest.mark.asyncio
    async def test_get_protocol_tvl(self, client):
        """测试获取协议TVL"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            # summary格式：多个协议条目
            mock_fetch.return_value = (
                [
                    {
                        "name": "Uniswap V3",
                        "slug": "uniswap-v3",
                        "parentProtocolSlug": "uniswap",
                        "tvl": 2000000000,
                        "chainTvls": {"Ethereum": 1500000000, "Arbitrum": 500000000},
                        "change_1d": 1.5,
                        "change_7d": 3.0,
                    },
                    {
                        "name": "Uniswap V2",
                        "slug": "uniswap-v2",
                        "parentProtocolSlug": "uniswap",
                        "tvl": 1000000000,
                        "chainTvls": {"Ethereum": 800000000, "Polygon": 200000000},
                        "change_1d": -0.5,
                        "change_7d": 1.0,
                    },
                ],
                mock_meta,
            )

            data, meta = await client.get_protocol_tvl("uniswap")

            mock_fetch.assert_called_once_with(
                endpoint="/protocols",
                params={},
                data_type="protocols_summary",
                ttl_seconds=3600,
            )

            # 聚合结果校验
            assert data["protocol"] == "uniswap"
            assert data["tvl_usd"] == 3000000000
            assert data["chain_breakdown"]["Ethereum"] == 2300000000
            assert data["chain_breakdown"]["Arbitrum"] == 500000000
            assert data["chain_breakdown"]["Polygon"] == 200000000

    @pytest.mark.asyncio
    async def test_get_protocol_fees(self, client):
        """测试获取协议费用"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_protocol_fees("aave")

            mock_fetch.assert_called_once_with(
                endpoint="/summary/fees/aave",
                params={},
                data_type="protocol_fees",
                ttl_seconds=3600,
            )

    @pytest.mark.asyncio
    async def test_get_stablecoins(self, client):
        """测试获取稳定币统计"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ([], mock_meta)

            await client.get_stablecoins()

            mock_fetch.assert_called_once_with(
                endpoint="/stablecoins",
                params={},
                data_type="stablecoins",
                ttl_seconds=1800,
            )

    @pytest.mark.asyncio
    async def test_get_cex_all(self, client):
        """测试获取所有CEX储备"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ([], mock_meta)

            await client.get_cex_all()

            mock_fetch.assert_called_once_with(
                endpoint="/protocols",
                params={"category": "CEX"},
                data_type="cex_list",
                ttl_seconds=600,
            )

    @pytest.mark.asyncio
    async def test_get_cex_reserves_specific(self, client):
        """测试获取特定交易所储备"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_cex_reserves("binance")

            mock_fetch.assert_called_once_with(
                endpoint="/protocol/binance",
                params={},
                data_type="cex_single",
                ttl_seconds=600,
            )

    @pytest.mark.asyncio
    async def test_get_cex_reserves_all(self, client):
        """测试获取所有交易所储备"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_cex_reserves(None)

            mock_fetch.assert_called_once_with(
                endpoint="/protocols",
                params={},
                data_type="cex_all",
                ttl_seconds=600,
            )

    @pytest.mark.asyncio
    async def test_get_bridge_volumes_specific(self, client):
        """测试获取特定桥接交易量"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_bridge_volumes("stargate")

            mock_fetch.assert_called_once_with(
                endpoint="/bridge/stargate",
                params={},
                data_type="bridge",
                ttl_seconds=1800,
            )

    @pytest.mark.asyncio
    async def test_get_bridge_volumes_all(self, client):
        """测试获取所有桥接交易量"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_bridge_volumes(None)

            mock_fetch.assert_called_once_with(
                endpoint="/bridges",
                params={},
                data_type="bridge",
                ttl_seconds=1800,
            )

    @pytest.mark.asyncio
    async def test_get_yields(self, client):
        """测试获取借贷收益率"""
        mock_data = [
            {"pool": "pool1", "symbol": "ETH", "project": "aave"},
            {"pool": "pool2", "symbol": "USDC", "project": "compound"},
        ]

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = (mock_data, mock_meta)

            data, meta = await client.get_yields()

            # 验证使用yields.llama.fi
            assert client.base_url == "https://api.llama.fi"  # 应该恢复原始URL

    @pytest.mark.asyncio
    async def test_get_yields_with_symbol_filter(self, client):
        """测试按资产过滤收益率"""
        mock_data = [
            {"pool": "pool1", "symbol": "ETH", "project": "aave"},
            {"pool": "pool2", "symbol": "USDC", "project": "compound"},
            {"pool": "pool3", "symbol": "ETH", "project": "compound"},
        ]

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = (mock_data, mock_meta)

            data, meta = await client.get_yields(symbol="ETH")

            # 验证过滤结果
            assert len(data) == 2
            assert all(d["symbol"] == "ETH" for d in data)

    @pytest.mark.asyncio
    async def test_get_yields_with_protocol_filter(self, client):
        """测试按协议过滤收益率"""
        mock_data = [
            {"pool": "pool1", "symbol": "ETH", "project": "aave"},
            {"pool": "pool2", "symbol": "USDC", "project": "compound"},
            {"pool": "pool3", "symbol": "ETH", "project": "aave"},
        ]

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = (mock_data, mock_meta)

            data, meta = await client.get_yields(protocol="aave")

            assert len(data) == 2
            assert all("aave" in d["project"].lower() for d in data)

    @pytest.mark.asyncio
    async def test_get_borrow_rates(self, client):
        """测试获取借贷利率"""
        mock_data = [
            {
                "pool": "pool1",
                "symbol": "ETH",
                "project": "aave",
                "apyBase": 1.5,
                "apyReward": 0.5,
                "tvlUsd": 1000000,
            },
        ]

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = (mock_data, mock_meta)

            data, meta = await client.get_borrow_rates("ETH")

            assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_yields_restores_base_url(self, client):
        """测试get_yields后恢复原始base_url"""
        original_url = client.base_url

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ([], mock_meta)

            await client.get_yields()

            # 验证恢复原始URL
            assert client.base_url == original_url

    @pytest.mark.asyncio
    async def test_get_yields_restores_base_url_on_error(self, client):
        """测试get_yields出错时也恢复base_url"""
        original_url = client.base_url

        with patch.object(client, "fetch") as mock_fetch:
            mock_fetch.side_effect = Exception("API Error")

            with pytest.raises(Exception):
                await client.get_yields()

            # 验证恢复原始URL
            assert client.base_url == original_url

    def test_transform_protocol_tvl(self, client):
        """测试协议TVL数据转换"""
        raw_data = {
            "name": "Uniswap",
            "tvl": 5000000000,
            "chainTvls": {
                "ethereum": 3000000000,
                "arbitrum": 1500000000,
                "polygon": 500000000,
            }
        }

        result = client.transform(raw_data, "protocol_tvl")

        assert result["protocol"] == "Uniswap"
        assert result["tvl_usd"] == 5000000000

    def test_transform_stablecoins(self, client):
        """测试稳定币数据转换"""
        raw_data = {
            "peggedAssets": [
                {
                    "name": "USDT",
                    "symbol": "USDT",
                    "circulating": {"peggedUSD": 80000000000},
                },
                {
                    "name": "USDC",
                    "symbol": "USDC",
                    "circulating": {"peggedUSD": 25000000000},
                },
            ]
        }

        result = client.transform(raw_data, "stablecoins")

        assert len(result) == 2
        assert result[0]["stablecoin"] == "USDT"
        assert result[0]["total_supply"] == 80000000000

    def test_transform_cex_reserves(self, client):
        """测试CEX储备数据转换"""
        raw_data = {
            "name": "Binance",
            "tvl": 50000000000,
            "tokens": [
                {"symbol": "BTC", "tvl": 20000000000},
                {"symbol": "ETH", "tvl": 15000000000},
            ]
        }

        result = client.transform(raw_data, "cex_single")

        assert result["exchange"] == "Binance"
        assert result["total_reserves_usd"] == 50000000000

    def test_transform_bridge(self, client):
        """测试桥接数据转换"""
        raw_data = {
            "displayName": "Stargate",
            "lastDayVolume": 100000000,
            "dayBeforeLastVolume": 90000000,
        }

        result = client.transform(raw_data, "bridge")

        assert result["bridge"] == "Stargate"
        assert result["volume_24h_usd"] == 100000000

    def test_transform_unknown_type(self, client):
        """测试未知数据类型"""
        raw_data = {"test": "data"}
        result = client.transform(raw_data, "unknown")
        assert result == raw_data
