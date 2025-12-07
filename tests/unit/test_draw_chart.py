"""
draw_chart 工具单元测试
"""
from datetime import datetime

import pytest

from src.core.models import DrawChartInput
from src.tools.chart import DrawChartTool


class TestDrawChartTool:
    """draw_chart 工具测试（客户端提供完整 Plotly 配置）"""

    @pytest.fixture
    def tool(self):
        """创建 DrawChartTool 实例"""
        return DrawChartTool()

    @pytest.mark.asyncio
    async def test_execute_uses_client_config_and_counts_points(self, tool):
        """测试使用客户端提供的 Plotly 配置并统计数据点数量"""
        config = {
            "layout": {
                "title": {"text": "ETH/USD 价格走势 (1年)"},
            },
            "data": [
                {
                    "type": "candlestick",
                    "x": [
                        "2025-01-01T00:00:00Z",
                        "2025-01-02T00:00:00Z",
                    ],
                    "open": [1000.0, 1020.0],
                    "high": [1030.0, 1050.0],
                    "low": [990.0, 1010.0],
                    "close": [1020.0, 1040.0],
                    "name": "ETH/USD",
                }
            ],
        }

        params = DrawChartInput(
            symbol="ETH",
            chart_type="candlestick",
            timeframe="1y",
            indicators=["MA20", "MA50"],
            config=config,
            title="ETH价格走势分析 (1年)",
        )

        result = await tool.execute(params)

        assert result.symbol == "ETH"
        assert result.chart_type == "candlestick"
        assert result.chart.chart_config == config
        assert result.chart.data_points == 2
        assert result.chart.warnings == []

    @pytest.mark.asyncio
    async def test_execute_handles_empty_config(self, tool):
        """测试空配置时的处理"""
        params = DrawChartInput(
            symbol="BTC",
            chart_type="line",
            config={},  # 没有 data / layout
        )

        result = await tool.execute(params)

        assert result.chart.data_points == 0
        assert len(result.chart.warnings) == 1
        assert "No data points" in result.chart.warnings[0]

    def test_calculate_ma(self):
        """测试MA计算"""
        tool = DrawChartTool()
        prices = [100, 102, 104, 106, 108, 110, 112, 114, 116, 118,
                  120, 122, 124, 126, 128, 130, 132, 134, 136, 138]

        ma = tool._calculate_ma(prices, period=5)

        # 前4个应该是None
        assert ma[0] is None
        assert ma[3] is None

        # 第5个开始有值
        assert ma[4] == 104.0  # (100+102+104+106+108)/5
        assert ma[5] == 106.0  # (102+104+106+108+110)/5

    def test_calculate_rsi(self):
        """测试RSI计算"""
        tool = DrawChartTool()
        # 模拟价格上涨序列
        prices = [100 + i for i in range(30)]

        rsi = tool._calculate_rsi(prices, period=14)

        # 前14个应该是None
        for i in range(14):
            assert rsi[i] is None

        # RSI应该在0-100之间
        for i in range(14, len(rsi)):
            if rsi[i] is not None:
                assert 0 <= rsi[i] <= 100

    def test_calculate_rsi_insufficient_data(self):
        """测试数据不足时的RSI计算"""
        tool = DrawChartTool()
        prices = [100, 101, 102]  # 少于14个数据点

        rsi = tool._calculate_rsi(prices, period=14)

        # 所有值都应该是None
        assert all(v is None for v in rsi)

    def test_generate_mock_data(self):
        """测试mock数据生成"""
        tool = DrawChartTool()

        data = tool._generate_mock_data("BTC/USDT", "1h")

        assert len(data) == 100
        assert all("time" in d for d in data)
        assert all("open" in d for d in data)
        assert all("high" in d for d in data)
        assert all("low" in d for d in data)
        assert all("close" in d for d in data)
        assert all("volume" in d for d in data)

        # 验证high >= low
        for d in data:
            assert d["high"] >= d["low"]

    def test_generate_chart_config_empty_data(self):
        """测试空数据生成图表配置"""
        tool = DrawChartTool()

        config = tool._generate_chart_config("line", [], [], "BTC/USDT")

        assert config["data"] == []
        assert config["layout"] == {}
