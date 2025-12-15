"""
market_microstructure工具单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.models import (
    MarketMicrostructureInput,
    SourceMeta,
)
from src.tools.market import MarketMicrostructureTool
from src.tools.market.calculators import (
    VolumeProfileCalculator,
    SlippageEstimator,
    TakerFlowAnalyzer,
)


class TestMarketMicrostructureTool:
    """market_microstructure工具测试"""

    @pytest.fixture
    def mock_binance_client(self):
        """模拟Binance客户端"""
        client = AsyncMock()

        # 模拟ticker响应
        client.get_ticker.return_value = (
            {
                "symbol": "BTCUSDT",
                "exchange": "binance",
                "last_price": 95000.0,
                "bid": 94999.0,
                "ask": 95001.0,
                "spread_bps": 2.1,
                "volume_24h": 12345.67,
                "quote_volume_24h": 1234567890.0,
                "price_change_24h": 1500.0,
                "price_change_percent_24h": 1.6,
                "high_24h": 96000.0,
                "low_24h": 93000.0,
                "timestamp": "2025-11-18T12:00:00Z",
            },
            SourceMeta(
                provider="binance",
                endpoint="/api/v3/ticker/24hr",
                as_of_utc="2025-11-18T12:00:00Z",
                ttl_seconds=5,
            ),
        )

        # 模拟orderbook响应
        client.get_orderbook.return_value = (
            {
                "symbol": "BTCUSDT",
                "exchange": "binance",
                "timestamp": 1700308800000,
                "bids": [
                    {"price": 94999.0, "quantity": 1.5, "total": 1.5},
                    {"price": 94998.0, "quantity": 2.0, "total": 3.5},
                ],
                "asks": [
                    {"price": 95001.0, "quantity": 1.2, "total": 1.2},
                    {"price": 95002.0, "quantity": 1.8, "total": 3.0},
                ],
                "mid_price": 95000.0,
                "spread_bps": 2.1,
                "bid_depth_10": 142498.5,
                "ask_depth_10": 114001.2,
                "imbalance_ratio": 1.25,
            },
            SourceMeta(
                provider="binance",
                endpoint="/api/v3/depth",
                as_of_utc="2025-11-18T12:00:00Z",
                ttl_seconds=1,
            ),
        )

        return client

    @pytest.fixture
    def tool(self, mock_binance_client):
        """创建工具实例"""
        return MarketMicrostructureTool(binance_client=mock_binance_client)

    @pytest.mark.asyncio
    async def test_fetch_ticker_only(self, tool):
        """测试只获取ticker"""
        params = MarketMicrostructureInput(
            symbol="BTC/USDT", include_fields=["ticker"]
        )

        result = await tool.execute(params)

        assert result.symbol == "BTCUSDT"
        assert result.data.ticker is not None
        assert result.data.ticker.last_price == 95000.0
        assert result.data.ticker.exchange == "binance"
        assert result.data.orderbook is None
        assert len(result.source_meta) >= 1

    @pytest.mark.asyncio
    async def test_fetch_ticker_and_orderbook(self, tool):
        """测试获取ticker和orderbook"""
        params = MarketMicrostructureInput(
            symbol="BTC/USDT", include_fields=["ticker", "orderbook"]
        )

        result = await tool.execute(params)

        assert result.symbol == "BTCUSDT"
        assert result.data.ticker is not None
        assert result.data.orderbook is not None
        assert result.data.orderbook.mid_price == 95000.0
        assert len(result.data.orderbook.bids) == 2
        assert len(result.data.orderbook.asks) == 2
        # 深度参数默认应为 100（用于更可靠的订单簿/滑点分析）
        tool.binance.get_orderbook.assert_awaited_with("BTCUSDT", 100)

    def test_symbol_normalization(self, tool):
        """测试交易对符号标准化"""
        # 测试各种输入格式
        assert tool._normalize_symbol("BTC/USDT") == "BTCUSDT"
        assert tool._normalize_symbol("btc/usdt") == "BTCUSDT"
        assert tool._normalize_symbol("BTCUSDT") == "BTCUSDT"
        assert tool._normalize_symbol("BTC") == "BTCUSDT"


class TestVolumeProfileCalculator:
    """成交量价格分布计算器测试"""

    def test_calculate_volume_profile(self):
        """测试VP计算"""
        trades = [
            {"price": 95000, "qty": 1.0, "side": "buy"},
            {"price": 95010, "qty": 2.0, "side": "sell"},
            {"price": 95005, "qty": 1.5, "side": "buy"},
            {"price": 95020, "qty": 0.5, "side": "sell"},
        ]

        calculator = VolumeProfileCalculator()
        result = calculator.calculate(trades, bucket_size=10)

        assert "buckets" in result
        assert "poc_price" in result
        assert "value_area_high" in result
        assert "value_area_low" in result
        assert len(result["buckets"]) > 0

    def test_empty_trades(self):
        """测试空成交记录"""
        calculator = VolumeProfileCalculator()
        result = calculator.calculate([], bucket_size=10)

        assert result["buckets"] == []
        assert result["poc_price"] == 0


class TestSlippageEstimator:
    """滑点估算器测试"""

    def test_estimate_buy_slippage(self):
        """测试买入滑点"""
        orderbook = {
            "bids": [],
            "asks": [
                {"price": 95001, "quantity": 1.0},
                {"price": 95002, "quantity": 2.0},
                {"price": 95010, "quantity": 5.0},
            ],
        }

        estimator = SlippageEstimator()
        result = estimator.estimate(
            orderbook, order_size_usd=200000, side="buy", current_price=95000
        )

        assert result["side"] == "buy"
        assert result["avg_fill_price"] > 95000  # 应该有滑点
        assert result["slippage_bps"] > 0
        assert result["orderbook_depth_sufficient"] is True

    def test_insufficient_depth(self):
        """测试深度不足"""
        orderbook = {
            "bids": [],
            "asks": [
                {"price": 95001, "quantity": 0.1},
            ],
        }

        estimator = SlippageEstimator()
        result = estimator.estimate(
            orderbook, order_size_usd=100000, side="buy", current_price=95000
        )

        assert result["orderbook_depth_sufficient"] is False


class TestTakerFlowAnalyzer:
    """主动买卖流分析器测试"""

    def test_analyze_flow(self):
        """测试买卖流分析"""
        trades = [
            {"side": "buy", "qty": 1.0, "quote_qty": 95000},
            {"side": "buy", "qty": 2.0, "quote_qty": 190000},
            {"side": "sell", "qty": 1.5, "quote_qty": 142500},
            {"side": "sell", "qty": 0.5, "quote_qty": 47500},
        ]

        analyzer = TakerFlowAnalyzer()
        result = analyzer.analyze(trades)

        assert result["total_buy_volume"] == 3.0
        assert result["total_sell_volume"] == 2.0
        assert result["total_buy_count"] == 2
        assert result["total_sell_count"] == 2
        assert result["net_volume"] == 1.0
        assert result["buy_ratio"] == 0.6

    def test_empty_trades(self):
        """测试空成交"""
        analyzer = TakerFlowAnalyzer()
        result = analyzer.analyze([])

        assert result["total_buy_volume"] == 0
        assert result["total_sell_volume"] == 0
        assert result["buy_ratio"] == 0
