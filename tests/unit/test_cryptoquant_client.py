"""
CryptoQuantClient 单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.models import SourceMeta
from src.data_sources.cryptoquant import CryptoQuantClient


class TestCryptoQuantClient:
    """CryptoQuantClient测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return CryptoQuantClient()

    def test_init(self, client):
        """测试初始化"""
        assert client.name == "cryptoquant"
        assert client.base_url == "https://api.cryptoquant.com"
        assert client.requires_api_key is True

    def test_normalize_symbol(self, client):
        """测试符号标准化"""
        assert client._normalize_symbol("BTC") == "btc"
        assert client._normalize_symbol("btc") == "btc"
        assert client._normalize_symbol("ETH") == "eth"
        assert client._normalize_symbol("USDT") == "usdt"
        assert client._normalize_symbol("UNKNOWN") == "unknown"

    # ==================== Active Addresses Tests ====================

    @pytest.mark.asyncio
    async def test_get_active_addresses(self, client):
        """测试获取活跃地址"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_active_addresses("BTC")

            mock_fetch.assert_called_once_with(
                endpoint="/v1/network/btc/active-addresses",
                params={"window": "day", "limit": 30},
                data_type="active_addresses",
                ttl_seconds=3600,
            )

    # ==================== MVRV Tests ====================

    @pytest.mark.asyncio
    async def test_get_mvrv_ratio(self, client):
        """测试获取MVRV比率"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_mvrv_ratio("BTC")

            mock_fetch.assert_called_once_with(
                endpoint="/v1/market/btc/mvrv",
                params={"window": "day", "limit": 30},
                data_type="mvrv",
                ttl_seconds=3600,
            )

    def test_transform_mvrv_extreme_overvalued(self, client):
        """测试MVRV转换 - 极度高估"""
        raw_data = {
            "result": {
                "data": [
                    {"date": "2024-01-01", "value": 4.0}
                ]
            }
        }
        result = client.transform(raw_data, "mvrv")
        assert result["mvrv_ratio"] == 4.0
        assert result["signal"] == "extreme_overvalued"

    def test_transform_mvrv_undervalued(self, client):
        """测试MVRV转换 - 低估"""
        raw_data = {
            "result": {
                "data": [
                    {"date": "2024-01-01", "value": 0.9}
                ]
            }
        }
        result = client.transform(raw_data, "mvrv")
        assert result["mvrv_ratio"] == 0.9
        assert result["signal"] == "undervalued"

    def test_transform_mvrv_extreme_undervalued(self, client):
        """测试MVRV转换 - 极度低估"""
        raw_data = {
            "result": {
                "data": [
                    {"date": "2024-01-01", "value": 0.7}
                ]
            }
        }
        result = client.transform(raw_data, "mvrv")
        assert result["signal"] == "extreme_undervalued"

    # ==================== SOPR Tests ====================

    @pytest.mark.asyncio
    async def test_get_sopr(self, client):
        """测试获取SOPR"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_sopr("BTC")

            mock_fetch.assert_called_once_with(
                endpoint="/v1/market/btc/sopr",
                params={"window": "day", "limit": 30},
                data_type="sopr",
                ttl_seconds=3600,
            )

    @pytest.mark.asyncio
    async def test_get_sopr_long_term_holder(self, client):
        """测试获取长期持有者SOPR"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_sopr("BTC", holder_type="long_term")

            mock_fetch.assert_called_once_with(
                endpoint="/v1/market/btc/sopr-lth",
                params={"window": "day", "limit": 30},
                data_type="sopr",
                ttl_seconds=3600,
            )

    @pytest.mark.asyncio
    async def test_get_sopr_short_term_holder(self, client):
        """测试获取短期持有者SOPR"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_sopr("BTC", holder_type="short_term")

            mock_fetch.assert_called_once_with(
                endpoint="/v1/market/btc/sopr-sth",
                params={"window": "day", "limit": 30},
                data_type="sopr",
                ttl_seconds=3600,
            )

    def test_transform_sopr_profit_taking(self, client):
        """测试SOPR转换 - 获利了结"""
        raw_data = {
            "result": {
                "data": [
                    {"date": "2024-01-01", "value": 1.1}
                ]
            }
        }
        result = client.transform(raw_data, "sopr")
        assert result["sopr"] == 1.1
        assert result["signal"] == "profit_taking"

    def test_transform_sopr_capitulation(self, client):
        """测试SOPR转换 - 投降"""
        raw_data = {
            "result": {
                "data": [
                    {"date": "2024-01-01", "value": 0.9}
                ]
            }
        }
        result = client.transform(raw_data, "sopr")
        assert result["sopr"] == 0.9
        assert result["signal"] == "capitulation"

    # ==================== Exchange Flow Tests ====================

    @pytest.mark.asyncio
    async def test_get_exchange_reserve(self, client):
        """测试获取交易所储备"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_exchange_reserve("BTC")

            mock_fetch.assert_called_once_with(
                endpoint="/v1/exchange/btc/reserve",
                params={"window": "day", "limit": 30},
                data_type="exchange_reserve",
                ttl_seconds=1800,
            )

    @pytest.mark.asyncio
    async def test_get_exchange_reserve_specific_exchange(self, client):
        """测试获取特定交易所储备"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_exchange_reserve("BTC", exchange="binance")

            mock_fetch.assert_called_once_with(
                endpoint="/v1/exchange/btc/reserve/binance",
                params={"window": "day", "limit": 30},
                data_type="exchange_reserve",
                ttl_seconds=1800,
            )

    @pytest.mark.asyncio
    async def test_get_exchange_netflow(self, client):
        """测试获取交易所净流量"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_exchange_netflow("BTC")

            mock_fetch.assert_called_once_with(
                endpoint="/v1/exchange/btc/netflow",
                params={"window": "day", "limit": 30},
                data_type="exchange_netflow",
                ttl_seconds=1800,
            )

    def test_transform_exchange_netflow_bearish(self, client):
        """测试净流量转换 - 看跌（净流入）"""
        raw_data = {
            "result": {
                "data": [
                    {"date": "2024-01-01", "value": 1000, "value_usd": 50000000}
                ]
            }
        }
        result = client.transform(raw_data, "exchange_netflow")
        assert result["netflow"] == 1000
        assert result["signal"] == "bearish"

    def test_transform_exchange_netflow_bullish(self, client):
        """测试净流量转换 - 看涨（净流出）"""
        raw_data = {
            "result": {
                "data": [
                    {"date": "2024-01-01", "value": -500, "value_usd": -25000000}
                ]
            }
        }
        result = client.transform(raw_data, "exchange_netflow")
        assert result["netflow"] == -500
        assert result["signal"] == "bullish"

    @pytest.mark.asyncio
    async def test_get_exchange_inflow(self, client):
        """测试获取交易所流入"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_exchange_inflow("BTC")

            mock_fetch.assert_called_once_with(
                endpoint="/v1/exchange/btc/inflow",
                params={"window": "day", "limit": 30},
                data_type="exchange_inflow",
                ttl_seconds=1800,
            )

    @pytest.mark.asyncio
    async def test_get_exchange_outflow(self, client):
        """测试获取交易所流出"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_exchange_outflow("BTC")

            mock_fetch.assert_called_once_with(
                endpoint="/v1/exchange/btc/outflow",
                params={"window": "day", "limit": 30},
                data_type="exchange_outflow",
                ttl_seconds=1800,
            )

    # ==================== Miner Tests ====================

    @pytest.mark.asyncio
    async def test_get_miner_reserve(self, client):
        """测试获取矿工储备"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_miner_reserve("BTC")

            mock_fetch.assert_called_once_with(
                endpoint="/v1/miner/btc/reserve",
                params={"window": "day", "limit": 30},
                data_type="miner_reserve",
                ttl_seconds=3600,
            )

    @pytest.mark.asyncio
    async def test_get_miner_outflow(self, client):
        """测试获取矿工流出"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_miner_outflow("BTC")

            mock_fetch.assert_called_once_with(
                endpoint="/v1/miner/btc/outflow",
                params={"window": "day", "limit": 30},
                data_type="miner_outflow",
                ttl_seconds=3600,
            )

    # ==================== Funding Rate Tests ====================

    @pytest.mark.asyncio
    async def test_get_funding_rate(self, client):
        """测试获取资金费率"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_funding_rate("BTC")

            mock_fetch.assert_called_once_with(
                endpoint="/v1/derivatives/btc/funding-rate",
                params={"limit": 30},
                data_type="funding_rate",
                ttl_seconds=300,
            )

    @pytest.mark.asyncio
    async def test_get_funding_rate_specific_exchange(self, client):
        """测试获取特定交易所资金费率"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_funding_rate("BTC", exchange="binance")

            mock_fetch.assert_called_once_with(
                endpoint="/v1/derivatives/btc/funding-rate/binance",
                params={"limit": 30},
                data_type="funding_rate",
                ttl_seconds=300,
            )

    def test_transform_funding_rate_extreme_long(self, client):
        """测试资金费率转换 - 极端多头"""
        raw_data = {
            "result": {
                "data": [
                    {"date": "2024-01-01", "value": 0.02}
                ]
            }
        }
        result = client.transform(raw_data, "funding_rate")
        assert result["funding_rate"] == 0.02
        assert result["signal"] == "extreme_long"

    def test_transform_funding_rate_extreme_short(self, client):
        """测试资金费率转换 - 极端空头"""
        raw_data = {
            "result": {
                "data": [
                    {"date": "2024-01-01", "value": -0.02}
                ]
            }
        }
        result = client.transform(raw_data, "funding_rate")
        assert result["funding_rate"] == -0.02
        assert result["signal"] == "extreme_short"

    def test_transform_funding_rate_neutral(self, client):
        """测试资金费率转换 - 中性"""
        raw_data = {
            "result": {
                "data": [
                    {"date": "2024-01-01", "value": 0.001}
                ]
            }
        }
        result = client.transform(raw_data, "funding_rate")
        assert result["signal"] == "neutral"

    # ==================== Helper Method Tests ====================

    def test_calculate_change(self, client):
        """测试变化百分比计算"""
        data_points = [
            {"date": "2024-01-01", "value": 100},
            {"date": "2024-01-02", "value": 110},
        ]
        change = client._calculate_change(data_points, 1)
        assert change == 10.0

    def test_calculate_change_with_zero(self, client):
        """测试变化百分比计算 - 除零处理"""
        data_points = [
            {"date": "2024-01-01", "value": 0},
            {"date": "2024-01-02", "value": 100},
        ]
        change = client._calculate_change(data_points, 1)
        assert change == 0.0

    def test_transform_empty_data(self, client):
        """测试空数据转换"""
        raw_data = {"result": {"data": []}}

        mvrv = client.transform(raw_data, "mvrv")
        assert mvrv["mvrv_ratio"] == 1.0
        assert mvrv["signal"] == "neutral"

        sopr = client.transform(raw_data, "sopr")
        assert sopr["sopr"] == 1.0

        netflow = client.transform(raw_data, "exchange_netflow")
        assert netflow["netflow"] == 0
        assert netflow["signal"] == "neutral"

    def test_transform_unknown_type(self, client):
        """测试未知数据类型"""
        raw_data = {"test": "data"}
        result = client.transform(raw_data, "unknown_type")
        assert result == raw_data
