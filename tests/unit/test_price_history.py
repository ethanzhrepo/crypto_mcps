"""
price_history 工具单元测试

测试技术指标计算和工具执行
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.models import (
    PriceHistoryIncludeIndicator,
    PriceHistoryInput,
    PriceHistoryOutput,
    SourceMeta,
)
from src.tools.market.indicators import (
    calculate_sma,
    calculate_ema,
    calculate_rsi,
    calculate_macd,
    calculate_bollinger,
    calculate_atr,
    calculate_volatility,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    find_support_resistance,
    calculate_price_changes,
)
from src.tools.market.price_history import PriceHistoryTool


class TestIndicatorCalculations:
    """技术指标计算测试"""

    @pytest.fixture
    def sample_closes(self):
        """示例收盘价数据（100个点）"""
        import random
        random.seed(42)
        # 模拟价格波动
        prices = [100.0]
        for _ in range(99):
            change = random.uniform(-2, 2.5)
            prices.append(max(50, prices[-1] + change))
        return prices

    @pytest.fixture
    def sample_ohlcv(self, sample_closes):
        """示例OHLCV数据"""
        highs = [c * 1.02 for c in sample_closes]
        lows = [c * 0.98 for c in sample_closes]
        return {
            "opens": [c * 0.99 for c in sample_closes],
            "highs": highs,
            "lows": lows,
            "closes": sample_closes,
            "volumes": [1000.0] * len(sample_closes),
        }

    def test_calculate_sma(self, sample_closes):
        """测试SMA计算"""
        result = calculate_sma(sample_closes, periods=[5, 10, 20])
        
        assert "sma_5" in result
        assert "sma_10" in result
        assert "sma_20" in result
        
        # 前4个值应为None（不足5个点）
        assert result["sma_5"][:4] == [None, None, None, None]
        # 第5个值应该存在
        assert result["sma_5"][4] is not None
        
        # 验证SMA计算正确性
        expected_sma_5_at_4 = sum(sample_closes[:5]) / 5
        assert abs(result["sma_5"][4] - expected_sma_5_at_4) < 0.01

    def test_calculate_ema(self, sample_closes):
        """测试EMA计算"""
        result = calculate_ema(sample_closes, periods=[12, 26])
        
        assert "ema_12" in result
        assert "ema_26" in result
        
        # EMA从第一个点就有值（使用ewm）
        assert len(result["ema_12"]) == len(sample_closes)

    def test_calculate_rsi(self, sample_closes):
        """测试RSI计算"""
        result = calculate_rsi(sample_closes, period=14)
        
        assert "rsi_14" in result
        assert "current" in result
        
        # RSI值应该在0-100之间
        for val in result["rsi_14"]:
            if val is not None:
                assert 0 <= val <= 100

    def test_calculate_macd(self, sample_closes):
        """测试MACD计算"""
        result = calculate_macd(sample_closes, fast=12, slow=26, signal=9)
        
        assert "macd_line" in result
        assert "signal_line" in result
        assert "histogram" in result
        assert "current_signal" in result
        
        # current_signal应该是有效值
        assert result["current_signal"] in ["bullish", "bearish", "neutral", "bullish_crossover", "bearish_crossover"]

    def test_calculate_bollinger(self, sample_closes):
        """测试布林带计算"""
        result = calculate_bollinger(sample_closes, period=20, std_dev=2.0)
        
        assert "upper" in result
        assert "middle" in result
        assert "lower" in result
        assert "bandwidth" in result
        
        # 验证上轨 > 中轨 > 下轨
        for i in range(20, len(sample_closes)):
            if result["upper"][i] and result["middle"][i] and result["lower"][i]:
                assert result["upper"][i] >= result["middle"][i] >= result["lower"][i]

    def test_calculate_atr(self, sample_ohlcv):
        """测试ATR计算"""
        result = calculate_atr(
            sample_ohlcv["highs"],
            sample_ohlcv["lows"],
            sample_ohlcv["closes"],
            period=14
        )
        
        assert "atr_14" in result
        assert "current" in result
        
        # ATR应该是正值
        for val in result["atr_14"]:
            if val is not None:
                assert val >= 0

    def test_calculate_volatility(self, sample_closes):
        """测试波动率计算"""
        vol_30d = calculate_volatility(sample_closes, window=30)
        vol_90d = calculate_volatility(sample_closes, window=90)
        
        # 波动率应该是正值
        assert vol_30d is not None
        assert vol_30d > 0
        
        # 90日波动率也应该存在
        assert vol_90d is not None

    def test_calculate_max_drawdown(self, sample_closes):
        """测试最大回撤计算"""
        dd_30 = calculate_max_drawdown(sample_closes, window=30)
        
        # 最大回撤应该是负数或0
        assert dd_30 is not None
        assert dd_30 <= 0

    def test_calculate_sharpe_ratio(self, sample_closes):
        """测试夏普比率计算"""
        sharpe = calculate_sharpe_ratio(sample_closes, window=90)
        
        # 夏普比率应该存在
        assert sharpe is not None

    def test_find_support_resistance(self, sample_closes, sample_ohlcv):
        """测试支撑阻力位查找"""
        support, resistance = find_support_resistance(
            sample_closes,
            sample_ohlcv["highs"],
            sample_ohlcv["lows"],
            num_levels=3
        )
        
        # 应该返回列表
        assert isinstance(support, list)
        assert isinstance(resistance, list)

    def test_calculate_price_changes(self, sample_closes):
        """测试价格变化计算"""
        result = calculate_price_changes(sample_closes)
        
        assert "price_change_7d_pct" in result
        assert "price_change_30d_pct" in result
        assert "current_vs_ath_pct" in result
        assert "current_vs_atl_pct" in result


class TestPriceHistoryTool:
    """PriceHistoryTool 测试"""

    @pytest.fixture
    def mock_binance_client(self):
        """Mock Binance客户端"""
        client = MagicMock()
        return client

    @pytest.fixture
    def tool(self, mock_binance_client):
        """创建工具实例"""
        return PriceHistoryTool(
            binance_client=mock_binance_client,
            okx_client=None,
        )

    @pytest.mark.asyncio
    async def test_execute_with_mocked_data(self, tool, mock_binance_client):
        """测试工具执行（使用mock数据）"""
        # 模拟K线数据
        mock_klines = [
            {
                "open_time": 1700000000000 + i * 86400000,
                "open": 100.0 + i,
                "high": 102.0 + i,
                "low": 98.0 + i,
                "close": 101.0 + i,
                "volume": 1000.0,
            }
            for i in range(100)
        ]
        
        mock_meta = SourceMeta(
            provider="binance",
            endpoint="/api/v3/klines",
            as_of_utc=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=3600,
        )
        
        mock_binance_client.get_klines = AsyncMock(return_value=(mock_klines, mock_meta))
        
        # 执行工具
        params = PriceHistoryInput(
            symbol="BTC/USDT",
            interval="1d",
            lookback_days=100,
            include_indicators=[PriceHistoryIncludeIndicator.SMA, PriceHistoryIncludeIndicator.RSI],
        )
        
        result = await tool.execute(params)
        
        # 验证返回类型
        assert isinstance(result, PriceHistoryOutput)
        assert result.symbol == "BTC/USDT"
        assert result.interval == "1d"
        assert result.data_points == 100
        
        # 验证指标存在
        assert result.indicators.sma is not None
        assert result.indicators.rsi is not None

    @pytest.mark.asyncio
    async def test_execute_with_all_indicators(self, tool, mock_binance_client):
        """测试执行所有指标"""
        mock_klines = [
            {
                "open_time": 1700000000000 + i * 86400000,
                "open": 100.0 + i * 0.5,
                "high": 102.0 + i * 0.5,
                "low": 98.0 + i * 0.5,
                "close": 101.0 + i * 0.5,
                "volume": 1000.0,
            }
            for i in range(200)
        ]
        
        mock_meta = SourceMeta(
            provider="binance",
            endpoint="/api/v3/klines",
            as_of_utc=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=3600,
        )
        
        mock_binance_client.get_klines = AsyncMock(return_value=(mock_klines, mock_meta))
        
        params = PriceHistoryInput(
            symbol="ETH/USDT",
            interval="1d",
            lookback_days=200,
            include_indicators=[PriceHistoryIncludeIndicator.ALL],
        )
        
        result = await tool.execute(params)
        
        # 验证所有指标都存在
        assert result.indicators.sma is not None
        assert result.indicators.ema is not None
        assert result.indicators.rsi is not None
        assert result.indicators.macd is not None
        assert result.indicators.bollinger is not None
        assert result.indicators.atr is not None
        
        # 验证统计数据
        assert result.statistics.volatility_30d is not None or result.statistics.volatility_90d is not None

    @pytest.mark.asyncio
    async def test_execute_with_custom_params(self, tool, mock_binance_client):
        """测试自定义指标参数"""
        mock_klines = [
            {
                "open_time": 1700000000000 + i * 86400000,
                "open": 100.0,
                "high": 102.0,
                "low": 98.0,
                "close": 100.0 + (i % 10),
                "volume": 1000.0,
            }
            for i in range(100)
        ]
        
        mock_meta = SourceMeta(
            provider="binance",
            endpoint="/api/v3/klines",
            as_of_utc=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=3600,
        )
        
        mock_binance_client.get_klines = AsyncMock(return_value=(mock_klines, mock_meta))
        
        params = PriceHistoryInput(
            symbol="BTC/USDT",
            interval="4h",
            lookback_days=30,
            include_indicators=[PriceHistoryIncludeIndicator.SMA],
            indicator_params={"sma_periods": [10, 30]},
        )
        
        result = await tool.execute(params)
        
        # 验证自定义SMA周期
        assert "sma_10" in result.indicators.sma
        assert "sma_30" in result.indicators.sma

    def test_input_validation(self):
        """测试输入验证"""
        # 正常输入
        params = PriceHistoryInput(
            symbol="BTC/USDT",
            interval="1d",
            lookback_days=365,
        )
        assert params.symbol == "BTC/USDT"
        
        # lookback_days边界测试
        with pytest.raises(Exception):
            PriceHistoryInput(symbol="BTC", lookback_days=2000)  # 超过最大值

        with pytest.raises(Exception):
            PriceHistoryInput(symbol="BTC", lookback_days=5)  # 低于最小值
