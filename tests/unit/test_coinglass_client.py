"""
CoinglassClient 单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.models import LiquidationsData, SourceMeta
from src.data_sources.coinglass import CoinglassClient


class TestCoinglassClient:
    """CoinglassClient测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return CoinglassClient(api_key="test_api_key")

    @pytest.fixture
    def client_without_key(self):
        """创建无API密钥的客户端"""
        return CoinglassClient()

    def test_init_with_api_key(self, client):
        """测试使用API密钥初始化"""
        assert client.api_key == "test_api_key"
        assert client.name == "coinglass"
        assert client.base_url == "https://open-api.coinglass.com/public/v2"

    def test_get_headers_with_key(self, client):
        """测试带API密钥的请求头"""
        headers = client._get_headers()
        assert headers["coinglassSecret"] == "test_api_key"
        assert headers["Accept"] == "application/json"

    def test_get_headers_without_key(self, client_without_key):
        """测试无API密钥的请求头"""
        headers = client_without_key._get_headers()
        assert "coinglassSecret" not in headers

    @pytest.mark.asyncio
    async def test_get_liquidation_history(self, client):
        """测试获取清算历史数据"""
        mock_response = {
            "code": "0",
            "msg": "success",
            "data": [
                {
                    "symbol": "BTC",
                    "exchangeName": "Binance",
                    "side": 1,  # LONG
                    "price": 45000.0,
                    "vol": 0.5,
                    "volUsd": 22500.0,
                    "createTime": 1700000000000,
                },
                {
                    "symbol": "BTC",
                    "exchangeName": "OKX",
                    "side": 0,  # SHORT
                    "price": 44500.0,
                    "vol": 1.0,
                    "volUsd": 44500.0,
                    "createTime": 1700000001000,
                },
            ]
        }

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = (
                client._transform_liquidation_history(mock_response),
                mock_meta
            )

            data, meta = await client.get_liquidation_history("BTC", time_type="h1")

            mock_fetch.assert_called_once_with(
                endpoint="/futures/liquidation_history",
                params={"symbol": "BTC", "time_type": "h1"},
                data_type="liquidation_history",
                ttl_seconds=60,
            )

    @pytest.mark.asyncio
    async def test_get_liquidation_history_with_exchange(self, client):
        """测试指定交易所获取清算历史"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({"events": [], "aggregated": {}}, mock_meta)

            await client.get_liquidation_history("ETH", time_type="h4", exchange="Binance")

            call_args = mock_fetch.call_args
            assert call_args[1]["params"]["ex"] == "Binance"

    @pytest.mark.asyncio
    async def test_get_liquidation_aggregated(self, client):
        """测试获取聚合清算数据"""
        mock_transformed = {
            "events": [
                {
                    "symbol": "BTC",
                    "exchange": "Binance",
                    "side": "LONG",
                    "price": 45000.0,
                    "quantity": 0.5,
                    "value_usd": 22500.0,
                    "timestamp": 1700000000000,
                }
            ],
            "aggregated": {
                "total_count": 1,
                "total_value_usd": 22500.0,
                "long_count": 1,
                "long_value_usd": 22500.0,
                "short_count": 0,
                "short_value_usd": 0.0,
            }
        }

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = (mock_transformed, mock_meta)

            data, meta = await client.get_liquidation_aggregated("BTC", lookback_hours=24)

            assert isinstance(data, LiquidationsData)
            assert data.symbol == "BTC"
            assert data.total_liquidations == 1
            assert data.total_value_usd == 22500.0
            assert data.long_liquidations == 1
            assert data.short_liquidations == 0
            assert len(data.events) == 1

    @pytest.mark.asyncio
    async def test_get_liquidation_aggregated_time_type_selection(self, client):
        """测试根据lookback_hours选择time_type"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({"aggregated": {}, "events": []}, mock_meta)

            # 测试1小时
            await client.get_liquidation_aggregated("BTC", lookback_hours=1)
            assert mock_fetch.call_args[1]["params"]["time_type"] == "h1"

            # 测试4小时
            await client.get_liquidation_aggregated("BTC", lookback_hours=4)
            assert mock_fetch.call_args[1]["params"]["time_type"] == "h4"

            # 测试12小时
            await client.get_liquidation_aggregated("BTC", lookback_hours=12)
            assert mock_fetch.call_args[1]["params"]["time_type"] == "h12"

            # 测试24小时
            await client.get_liquidation_aggregated("BTC", lookback_hours=24)
            assert mock_fetch.call_args[1]["params"]["time_type"] == "h24"

    @pytest.mark.asyncio
    async def test_get_liquidation_aggregated_empty_data(self, client):
        """测试聚合数据为空时返回默认值"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            data, meta = await client.get_liquidation_aggregated("BTC", lookback_hours=24)

            assert isinstance(data, LiquidationsData)
            assert data.total_liquidations == 0
            assert data.total_value_usd == 0.0
            assert len(data.events) == 0

    def test_transform_liquidation_history(self, client):
        """测试清算历史数据转换"""
        raw_data = {
            "code": "0",
            "msg": "success",
            "data": [
                {
                    "symbol": "BTC",
                    "exchangeName": "Binance",
                    "side": 1,
                    "price": 45000.0,
                    "vol": 0.5,
                    "volUsd": 22500.0,
                    "createTime": 1700000000000,
                },
                {
                    "symbol": "BTC",
                    "exchangeName": "OKX",
                    "side": 0,
                    "price": 44500.0,
                    "vol": 1.0,
                    "volUsd": 44500.0,
                    "createTime": 1700000001000,
                },
            ]
        }

        result = client._transform_liquidation_history(raw_data)

        assert len(result["events"]) == 2
        assert result["aggregated"]["total_count"] == 2
        assert result["aggregated"]["total_value_usd"] == 67000.0
        assert result["aggregated"]["long_count"] == 1
        assert result["aggregated"]["long_value_usd"] == 22500.0
        assert result["aggregated"]["short_count"] == 1
        assert result["aggregated"]["short_value_usd"] == 44500.0

        # 验证事件数据
        assert result["events"][0]["side"] == "LONG"
        assert result["events"][1]["side"] == "SHORT"

    def test_transform_liquidation_history_empty(self, client):
        """测试空数据转换"""
        result = client._transform_liquidation_history(None)
        assert result == {"events": [], "aggregated": {}}

        result = client._transform_liquidation_history({})
        assert result == {"events": [], "aggregated": {}}

    def test_transform_liquidation_history_invalid_data(self, client):
        """测试无效数据格式"""
        raw_data = {"data": "invalid"}
        result = client._transform_liquidation_history(raw_data)
        assert result["events"] == []
        assert result["aggregated"]["total_count"] == 0

    @pytest.mark.asyncio
    async def test_get_liquidation_chart(self, client):
        """测试获取清算图表数据"""
        mock_chart_data = [
            {"time": 1700000000, "longLiquidations": 100, "shortLiquidations": 50},
            {"time": 1700003600, "longLiquidations": 150, "shortLiquidations": 80},
        ]

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = (mock_chart_data, mock_meta)

            data, meta = await client.get_liquidation_chart("BTC", interval="h1")

            mock_fetch.assert_called_once_with(
                endpoint="/futures/liquidation_chart",
                params={"symbol": "BTC", "interval": "h1"},
                data_type="liquidation_chart",
                ttl_seconds=60,
            )

    @pytest.mark.asyncio
    async def test_health_check_success(self, client):
        """测试健康检查成功"""
        with patch.object(client, "get_liquidation_history") as mock_get:
            mock_get.return_value = ({}, MagicMock())

            result = await client.health_check()

            assert result is True
            mock_get.assert_called_once_with("BTC", time_type="h1")

    @pytest.mark.asyncio
    async def test_health_check_failure(self, client):
        """测试健康检查失败"""
        with patch.object(client, "get_liquidation_history") as mock_get:
            mock_get.side_effect = Exception("API Error")

            result = await client.health_check()

            assert result is False

    def test_symbol_uppercase_conversion(self, client):
        """测试符号自动转换为大写"""
        raw_data = {
            "code": "0",
            "data": [
                {
                    "symbol": "btc",
                    "exchangeName": "Binance",
                    "side": 1,
                    "price": 45000.0,
                    "vol": 0.5,
                    "volUsd": 22500.0,
                    "createTime": 1700000000000,
                }
            ]
        }

        result = client._transform_liquidation_history(raw_data)
        assert result["events"][0]["symbol"] == "btc"  # 原始数据保持

    @pytest.mark.asyncio
    async def test_events_limited_to_100(self, client):
        """测试事件数量限制为100"""
        # 创建150个事件
        events = [
            {
                "symbol": "BTC",
                "exchange": "Binance",
                "side": "LONG",
                "price": 45000.0,
                "quantity": 0.1,
                "value_usd": 4500.0,
                "timestamp": 1700000000000 + i,
            }
            for i in range(150)
        ]

        mock_transformed = {
            "events": events,
            "aggregated": {
                "total_count": 150,
                "total_value_usd": 675000.0,
                "long_count": 150,
                "long_value_usd": 675000.0,
                "short_count": 0,
                "short_value_usd": 0.0,
            }
        }

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = (mock_transformed, mock_meta)

            data, meta = await client.get_liquidation_aggregated("BTC", lookback_hours=24)

            assert len(data.events) == 100  # 限制为100个事件
