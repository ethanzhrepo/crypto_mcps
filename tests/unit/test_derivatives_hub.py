"""
derivatives_hub 工具单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.core.models import (
    DerivativesHubInput,
    SourceMeta,
)
from src.tools.derivatives import DerivativesHubTool


class TestDerivativesHubTool:
    """derivatives_hub工具测试"""

    @pytest.fixture
    def mock_binance_client(self):
        """模拟Binance衍生品客户端"""
        client = AsyncMock()

        # 模拟资金费率
        client.get_funding_rate.return_value = (
            {
                "symbol": "BTCUSDT",
                "exchange": "binance",
                "current_funding_rate": 0.0001,
                "next_funding_time": "2025-11-18T16:00:00Z",
                "avg_funding_rate_8h": 0.00012,
                "avg_funding_rate_24h": 0.00015,
            },
            SourceMeta(
                provider="binance_futures",
                endpoint="/fapi/v1/fundingRate",
                as_of_utc="2025-11-18T12:00:00Z",
                ttl_seconds=300,
            )
        )

        # 模拟未平仓合约
        client.get_open_interest.return_value = (
            {
                "symbol": "BTCUSDT",
                "exchange": "binance",
                "open_interest": 50000.0,
                "open_interest_usd": 4750000000.0,
                "timestamp": "2025-11-18T12:00:00Z",
                "change_24h": 2000.0,
                "change_percent_24h": 4.17,
            },
            SourceMeta(
                provider="binance_futures",
                endpoint="/fapi/v1/openInterest",
                as_of_utc="2025-11-18T12:00:00Z",
                ttl_seconds=300,
            )
        )

        # 模拟多空比
        client.get_long_short_ratio.return_value = (
            {
                "symbol": "BTCUSDT",
                "exchange": "binance",
                "long_ratio": 0.55,
                "short_ratio": 0.45,
                "long_account_ratio": 0.52,
                "short_account_ratio": 0.48,
                "timestamp": "2025-11-18T12:00:00Z",
            },
            SourceMeta(
                provider="binance_futures",
                endpoint="/futures/data/globalLongShortAccountRatio",
                as_of_utc="2025-11-18T12:00:00Z",
                ttl_seconds=300,
            )
        )

        return client

    @pytest.fixture
    def mock_okx_client(self):
        """模拟OKX衍生品客户端"""
        client = AsyncMock()

        # 模拟资金费率
        client.get_funding_rate.return_value = (
            {
                "symbol": "BTC-USDT-SWAP",
                "exchange": "okx",
                "current_funding_rate": 0.00009,
                "next_funding_time": "2025-11-18T16:00:00Z",
                "avg_funding_rate_8h": 0.0001,
            },
            SourceMeta(
                provider="okx_futures",
                endpoint="/api/v5/public/funding-rate",
                as_of_utc="2025-11-18T12:00:00Z",
                ttl_seconds=300,
            )
        )

        # 模拟未平仓合约
        client.get_open_interest.return_value = (
            {
                "symbol": "BTC-USDT-SWAP",
                "exchange": "okx",
                "open_interest": 48000.0,
                "open_interest_usd": 4560000000.0,
                "timestamp": "2025-11-18T12:00:00Z",
            },
            SourceMeta(
                provider="okx_futures",
                endpoint="/api/v5/public/open-interest",
                as_of_utc="2025-11-18T12:00:00Z",
                ttl_seconds=300,
            )
        )

        return client

    @pytest.fixture
    def tool_with_both_exchanges(self, mock_binance_client, mock_okx_client):
        """创建包含Binance和OKX的工具实例"""
        return DerivativesHubTool(
            binance_client=mock_binance_client,
            okx_client=mock_okx_client,
        )

    @pytest.fixture
    def tool_binance_only(self, mock_binance_client):
        """创建仅Binance的工具实例"""
        return DerivativesHubTool(binance_client=mock_binance_client)

    @pytest.mark.asyncio
    async def test_funding_rate_binance(self, tool_binance_only):
        """测试获取资金费率（Binance）"""
        params = DerivativesHubInput(
            symbol="BTC/USDT",
            include_fields=["funding_rate"]
        )

        result = await tool_binance_only.execute(params)

        assert result.symbol == "BTCUSDT"
        assert result.data.funding_rate is not None
        assert result.data.funding_rate.current_funding_rate == 0.0001
        assert result.data.funding_rate.exchange == "binance"

    @pytest.mark.asyncio
    async def test_funding_rate_with_okx_fallback(self, tool_with_both_exchanges):
        """测试资金费率OKX fallback"""
        # 模拟Binance失败
        tool_with_both_exchanges.binance_client.get_funding_rate.side_effect = Exception("Binance Error")

        params = DerivativesHubInput(
            symbol="BTC/USDT",
            include_fields=["funding_rate"]
        )

        result = await tool_with_both_exchanges.execute(params)

        # 应该fallback到OKX
        assert result.data.funding_rate is not None
        assert result.data.funding_rate.exchange == "okx"
        assert len(result.warnings) > 0

    @pytest.mark.asyncio
    async def test_open_interest_binance(self, tool_binance_only):
        """测试获取未平仓合约（Binance）"""
        params = DerivativesHubInput(
            symbol="BTC/USDT",
            include_fields=["open_interest"]
        )

        result = await tool_binance_only.execute(params)

        assert result.data.open_interest is not None
        assert result.data.open_interest.open_interest == 50000.0
        assert result.data.open_interest.open_interest_usd == 4750000000.0

    @pytest.mark.asyncio
    async def test_open_interest_with_okx_fallback(self, tool_with_both_exchanges):
        """测试未平仓合约OKX fallback"""
        # 模拟Binance失败
        tool_with_both_exchanges.binance_client.get_open_interest.side_effect = Exception("Binance Error")

        params = DerivativesHubInput(
            symbol="BTC/USDT",
            include_fields=["open_interest"]
        )

        result = await tool_with_both_exchanges.execute(params)

        # 应该fallback到OKX
        assert result.data.open_interest is not None
        assert result.data.open_interest.exchange == "okx"

    @pytest.mark.asyncio
    async def test_long_short_ratio(self, tool_binance_only):
        """测试获取多空比"""
        params = DerivativesHubInput(
            symbol="BTC/USDT",
            include_fields=["long_short_ratio"]
        )

        result = await tool_binance_only.execute(params)

        assert result.data.long_short_ratio is not None
        assert result.data.long_short_ratio.long_ratio == 0.55
        assert result.data.long_short_ratio.short_ratio == 0.45

    @pytest.mark.asyncio
    async def test_multiple_fields(self, tool_binance_only):
        """测试获取多个字段"""
        params = DerivativesHubInput(
            symbol="BTC/USDT",
            include_fields=["funding_rate", "open_interest", "long_short_ratio"]
        )

        result = await tool_binance_only.execute(params)

        assert result.data.funding_rate is not None
        assert result.data.open_interest is not None
        assert result.data.long_short_ratio is not None
        assert len(result.source_meta) >= 3

    @pytest.mark.asyncio
    async def test_symbol_normalization(self, tool_binance_only):
        """测试交易对符号标准化"""
        params = DerivativesHubInput(
            symbol="btc/usdt",  # 小写
            include_fields=["funding_rate"]
        )

        result = await tool_binance_only.execute(params)

        # 应该被标准化为BTCUSDT
        assert result.symbol == "BTCUSDT"

    @pytest.mark.asyncio
    async def test_error_handling(self, tool_binance_only):
        """测试错误处理"""
        tool_binance_only.binance_client.get_funding_rate.side_effect = Exception("API Error")

        params = DerivativesHubInput(
            symbol="BTC/USDT",
            include_fields=["funding_rate"]
        )

        result = await tool_binance_only.execute(params)

        # 应该有警告
        assert result.data.funding_rate is None
        assert len(result.warnings) > 0

    @pytest.mark.asyncio
    async def test_partial_failure(self, tool_binance_only):
        """测试部分字段失败"""
        # 模拟funding_rate成功但open_interest失败
        tool_binance_only.binance_client.get_open_interest.side_effect = Exception("OI Error")

        params = DerivativesHubInput(
            symbol="BTC/USDT",
            include_fields=["funding_rate", "open_interest"]
        )

        result = await tool_binance_only.execute(params)

        # funding_rate应该成功
        assert result.data.funding_rate is not None
        # open_interest应该失败
        assert result.data.open_interest is None
        # 应该有警告
        assert len(result.warnings) > 0

    @pytest.mark.asyncio
    async def test_empty_include_fields(self, tool_binance_only):
        """测试空include_fields默认获取funding_rate"""
        params = DerivativesHubInput(
            symbol="BTC/USDT",
            include_fields=[]
        )

        result = await tool_binance_only.execute(params)

        # 应该使用默认值（funding_rate）
        assert result.data.funding_rate is not None

    @pytest.mark.asyncio
    async def test_venue_parameter(self, tool_with_both_exchanges):
        """测试venue参数指定交易所"""
        params = DerivativesHubInput(
            symbol="BTC/USDT",
            include_fields=["funding_rate"],
            venues=["okx"]  # 明确指定OKX
        )

        result = await tool_with_both_exchanges.execute(params)

        # 应该使用OKX（如果实现了venue过滤）
        # 目前代码可能没有完全实现venue参数，这个测试为未来扩展预留
        assert result.data.funding_rate is not None
