"""
macro_hub 工具单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from src.core.models import (
    MacroHubInput,
    FearGreedIndex,
    IndexData,
    CalendarEvent,
    MacroCalendar,
    SourceMeta,
)
from src.tools.macro import MacroHubTool


class TestMacroHubTool:
    """macro_hub工具测试"""

    @pytest.fixture
    def mock_macro_client(self):
        """模拟MacroDataClient"""
        client = AsyncMock()

        # 模拟恐惧贪婪指数响应
        client.get_fear_greed_index.return_value = (
            {
                "value": 75,
                "value_classification": "Greed",
                "timestamp": "2025-11-18T12:00:00Z",
                "time_until_update": "12 hours",
            },
            SourceMeta(
                provider="alternative.me",
                endpoint="/fng/",
                as_of_utc="2025-11-18T12:00:00Z",
                ttl_seconds=3600,
            )
        )

        # 模拟加密货币指数响应
        client.get_crypto_indices.return_value = (
            [
                {
                    "name": "Total Market Cap",
                    "symbol": "total_mcap",
                    "value": 3500000000000,
                    "change_24h": 50000000000,
                    "change_percent_24h": 1.45,
                    "timestamp": "2025-11-18T12:00:00Z",
                },
                {
                    "name": "BTC Dominance",
                    "symbol": "btc_dominance",
                    "value": 54.2,
                    "change_24h": 0.3,
                    "change_percent_24h": 0.55,
                    "timestamp": "2025-11-18T12:00:00Z",
                }
            ],
            SourceMeta(
                provider="coingecko",
                endpoint="/global",
                as_of_utc="2025-11-18T12:00:00Z",
                ttl_seconds=300,
            )
        )

        return client

    @pytest.fixture
    def mock_fred_client(self):
        """模拟FRED客户端"""
        client = AsyncMock()

        # 模拟通胀数据
        client.get_inflation_data.return_value = (
            {
                "cpi": {"value": 3.2, "date": "2025-10-01"},
                "pce": {"value": 2.8, "date": "2025-10-01"},
            },
            SourceMeta(
                provider="fred",
                endpoint="/series",
                as_of_utc="2025-11-18T12:00:00Z",
                ttl_seconds=86400,
            )
        )

        # 模拟就业数据
        client.get_employment_data.return_value = (
            {
                "unemployment_rate": {"value": 3.8, "date": "2025-10-01"},
                "nonfarm_payrolls": {"value": 150000, "date": "2025-10-01"},
            },
            SourceMeta(
                provider="fred",
                endpoint="/series",
                as_of_utc="2025-11-18T12:00:00Z",
                ttl_seconds=86400,
            )
        )

        # 模拟收益率曲线
        client.get_yield_curve.return_value = (
            {
                "treasury_2y": {"value": 4.5, "date": "2025-11-17"},
                "treasury_10y": {"value": 4.3, "date": "2025-11-17"},
                "treasury_30y": {"value": 4.4, "date": "2025-11-17"},
                "spread_10y_2y": -0.2,
            },
            SourceMeta(
                provider="fred",
                endpoint="/series",
                as_of_utc="2025-11-18T12:00:00Z",
                ttl_seconds=3600,
            )
        )

        # 模拟联储工具
        client.get_fed_tools.return_value = (
            {
                "tga": {"value": 750000000000, "date": "2025-11-17"},
                "rrp": {"value": 500000000000, "date": "2025-11-17"},
            },
            SourceMeta(
                provider="fred",
                endpoint="/series",
                as_of_utc="2025-11-18T12:00:00Z",
                ttl_seconds=86400,
            )
        )

        return client

    @pytest.fixture
    def mock_yfinance_client(self):
        """模拟YFinance客户端"""
        client = AsyncMock()

        # 模拟股指数据
        client.get_market_indices.return_value = (
            {
                "spx": {
                    "name": "S&P 500",
                    "symbol": "^GSPC",
                    "price": 5900.0,
                    "change": 50.0,
                    "change_percent": 0.85,
                },
                "vix": {
                    "name": "VIX",
                    "symbol": "^VIX",
                    "price": 14.5,
                    "change": -0.5,
                    "change_percent": -3.33,
                }
            },
            SourceMeta(
                provider="yfinance",
                endpoint="/v7/finance/quote",
                as_of_utc="2025-11-18T12:00:00Z",
                ttl_seconds=300,
            )
        )

        # 模拟大宗商品
        client.get_commodities.return_value = (
            {
                "gold": {
                    "name": "Gold",
                    "symbol": "GC=F",
                    "price": 2050.0,
                    "change": 10.0,
                    "change_percent": 0.49,
                }
            },
            SourceMeta(
                provider="yfinance",
                endpoint="/v7/finance/quote",
                as_of_utc="2025-11-18T12:00:00Z",
                ttl_seconds=300,
            )
        )

        # 模拟美元指数
        client.get_dollar_index.return_value = (
            {
                "symbol": "DX-Y.NYB",
                "price": 103.5,
                "change": -0.2,
                "change_percent": -0.19,
            },
            SourceMeta(
                provider="yfinance",
                endpoint="/v7/finance/quote",
                as_of_utc="2025-11-18T12:00:00Z",
                ttl_seconds=300,
            )
        )

        return client

    @pytest.fixture
    def mock_calendar_client(self):
        """模拟InvestingCalendarClient"""
        client = AsyncMock()

        client.get_upcoming_events.return_value = (
            [
                {
                    "event_name": "FOMC Meeting",
                    "country": "United States",
                    "date": "2025-11-20",
                    "time": "14:00",
                    "importance": 3,
                    "actual": None,
                    "forecast": None,
                    "previous": None,
                }
            ],
            SourceMeta(
                provider="investing.com",
                endpoint="/economic-calendar/",
                as_of_utc="2025-11-18T12:00:00Z",
                ttl_seconds=3600,
            )
        )

        return client

    @pytest.fixture
    def tool_with_all_clients(
        self, mock_macro_client, mock_fred_client, mock_yfinance_client, mock_calendar_client
    ):
        """创建包含所有客户端的工具实例"""
        return MacroHubTool(
            macro_client=mock_macro_client,
            fred_client=mock_fred_client,
            yfinance_client=mock_yfinance_client,
            calendar_client=mock_calendar_client,
        )

    @pytest.fixture
    def tool_basic(self, mock_macro_client, mock_calendar_client):
        """创建基础工具实例（无FRED/YFinance）"""
        return MacroHubTool(
            macro_client=mock_macro_client,
            calendar_client=mock_calendar_client,
        )

    @pytest.mark.asyncio
    async def test_fear_greed_mode(self, tool_basic):
        """测试fear_greed模式"""
        params = MacroHubInput(mode="fear_greed")

        result = await tool_basic.execute(params)

        assert result.data.fear_greed is not None
        assert result.data.fear_greed.value == 75
        assert result.data.fear_greed.value_classification == "Greed"
        assert len(result.source_meta) >= 1

    @pytest.mark.asyncio
    async def test_crypto_indices_mode(self, tool_basic):
        """测试crypto_indices模式"""
        params = MacroHubInput(mode="crypto_indices")

        result = await tool_basic.execute(params)

        assert result.data.crypto_indices is not None
        assert len(result.data.crypto_indices) == 2
        assert result.data.crypto_indices[0].name == "Total Market Cap"
        assert result.data.crypto_indices[1].symbol == "btc_dominance"

    @pytest.mark.asyncio
    async def test_dashboard_mode(self, tool_with_all_clients):
        """测试dashboard模式（获取所有数据）"""
        params = MacroHubInput(mode="dashboard")

        result = await tool_with_all_clients.execute(params)

        # 应该包含所有类型的数据
        assert result.data.fear_greed is not None
        assert result.data.crypto_indices is not None
        assert result.data.calendar is not None
        # crypto_indices应该包含FRED和YFinance的数据
        assert len(result.data.crypto_indices) > 2

    @pytest.mark.asyncio
    async def test_fed_mode_with_fred_client(self, tool_with_all_clients):
        """测试fed模式（有FRED客户端）"""
        params = MacroHubInput(mode="fed")

        result = await tool_with_all_clients.execute(params)

        # 应该包含FED数据
        assert result.data.crypto_indices is not None
        # 应该包含通胀、就业、收益率、联储工具数据
        assert len(result.data.crypto_indices) > 0

        # 验证包含预期的指标
        symbols = [idx.symbol for idx in result.data.crypto_indices]
        assert any("cpi" in s or "pce" in s for s in symbols)

    @pytest.mark.asyncio
    async def test_fed_mode_without_fred_client(self, tool_basic):
        """测试fed模式（无FRED客户端）"""
        params = MacroHubInput(mode="fed")

        result = await tool_basic.execute(params)

        # 应该有警告
        assert len(result.warnings) > 0
        assert any("FRED" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_indices_mode_with_yfinance_client(self, tool_with_all_clients):
        """测试indices模式（有YFinance客户端）"""
        params = MacroHubInput(mode="indices")

        result = await tool_with_all_clients.execute(params)

        # 应该包含市场指数数据
        assert result.data.crypto_indices is not None
        symbols = [idx.symbol for idx in result.data.crypto_indices]
        assert "^GSPC" in symbols or "DX-Y.NYB" in symbols

    @pytest.mark.asyncio
    async def test_indices_mode_without_yfinance_client(self, tool_basic):
        """测试indices模式（无YFinance客户端）"""
        params = MacroHubInput(mode="indices")

        result = await tool_basic.execute(params)

        # 应该有警告
        assert len(result.warnings) > 0
        assert any("Yahoo Finance" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_calendar_mode(self, tool_basic):
        """测试calendar模式"""
        params = MacroHubInput(
            mode="calendar",
            calendar_days=7,
            calendar_min_importance=2
        )

        result = await tool_basic.execute(params)

        assert result.data.calendar is not None
        assert result.data.calendar.count == 1
        assert result.data.calendar.days_ahead == 7
        assert result.data.calendar.min_importance == 2
        assert len(result.data.calendar.events) == 1
        assert result.data.calendar.events[0].event_name == "FOMC Meeting"

    @pytest.mark.asyncio
    async def test_error_handling(self, tool_basic):
        """测试错误处理"""
        # 模拟API错误
        tool_basic.macro_client.get_fear_greed_index.side_effect = Exception("API Error")

        params = MacroHubInput(mode="fear_greed")

        result = await tool_basic.execute(params)

        # 应该捕获错误并添加警告
        assert result.data.fear_greed is None
        assert len(result.warnings) > 0
        assert any("Fear & Greed" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_partial_failure(self, tool_with_all_clients):
        """测试部分失败（某些数据源失败）"""
        # 模拟FRED失败但其他正常
        tool_with_all_clients.fred_client.get_inflation_data.side_effect = Exception("FRED Error")

        params = MacroHubInput(mode="dashboard")

        result = await tool_with_all_clients.execute(params)

        # 应该仍然返回其他可用的数据
        assert result.data.fear_greed is not None
        assert result.data.crypto_indices is not None
        # 应该有警告
        assert len(result.warnings) > 0

    @pytest.mark.asyncio
    async def test_country_parameter(self, tool_basic):
        """测试country参数"""
        params = MacroHubInput(
            mode="calendar",
            country="United States",
            calendar_days=7
        )

        result = await tool_basic.execute(params)

        # country参数应该被传递（即使目前未使用）
        assert result.data.calendar is not None
