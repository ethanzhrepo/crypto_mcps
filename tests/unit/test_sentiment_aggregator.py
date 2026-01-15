"""
sentiment_aggregator 工具单元测试

测试情绪聚合功能
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.models import (
    SentimentAggregatorInput,
    SentimentAggregatorOutput,
    SentimentSource,
    SourceMeta,
)
from src.tools.sentiment.aggregator import (
    SentimentAggregatorTool,
    SOURCE_WEIGHTS,
    score_to_label,
)


class TestScoreToLabel:
    """情绪分数转标签测试"""

    def test_very_bearish(self):
        assert score_to_label(10) == "very_bearish"
        assert score_to_label(20) == "very_bearish"

    def test_bearish(self):
        assert score_to_label(30) == "bearish"
        assert score_to_label(40) == "bearish"

    def test_neutral(self):
        assert score_to_label(50) == "neutral"
        assert score_to_label(55) == "neutral"

    def test_bullish(self):
        assert score_to_label(70) == "bullish"
        assert score_to_label(80) == "bullish"

    def test_very_bullish(self):
        assert score_to_label(85) == "very_bullish"
        assert score_to_label(100) == "very_bullish"


class TestSourceWeights:
    """数据源权重测试"""

    def test_weights_sum_to_one(self):
        """权重总和应为1"""
        total = sum(SOURCE_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01

    def test_twitter_has_highest_weight(self):
        """Twitter应该有最高权重"""
        assert SOURCE_WEIGHTS[SentimentSource.TWITTER] >= max(
            SOURCE_WEIGHTS[SentimentSource.TELEGRAM],
            SOURCE_WEIGHTS[SentimentSource.NEWS],
            SOURCE_WEIGHTS[SentimentSource.REDDIT],
        )


class TestSentimentAggregatorTool:
    """SentimentAggregatorTool 测试"""

    @pytest.fixture
    def mock_telegram_tool(self):
        """Mock Telegram搜索工具"""
        tool = MagicMock()
        return tool

    @pytest.fixture
    def mock_grok_tool(self):
        """Mock Grok工具"""
        tool = MagicMock()
        return tool

    @pytest.fixture
    def mock_web_research_tool(self):
        """Mock Web研究工具"""
        tool = MagicMock()
        return tool

    @pytest.fixture
    def tool(self, mock_telegram_tool, mock_grok_tool, mock_web_research_tool):
        """创建工具实例"""
        return SentimentAggregatorTool(
            crypto_news_search_tool=mock_telegram_tool,
            grok_social_trace_tool=mock_grok_tool,
            web_research_tool=mock_web_research_tool,
        )

    @pytest.fixture
    def mock_telegram_response(self):
        """Mock Telegram响应"""
        response = MagicMock()
        response.results = [
            {"text": "BTC is going to moon! Very bullish!"},
            {"text": "Just bought more Bitcoin"},
            {"text": "Price is pumping right now"},
        ]
        return response

    @pytest.fixture
    def mock_grok_response(self):
        """Mock Grok响应"""
        response = MagicMock()
        response.is_likely_promotion = False
        response.deepsearch_insights = "Overall sentiment on Twitter is bullish for BTC."
        return response

    @pytest.fixture
    def mock_news_response(self):
        """Mock 新闻响应"""
        response = MagicMock()
        response.results = [
            {"title": "Bitcoin Surges Past $100K", "snippet": "BTC gains momentum", "source": "CoinDesk"},
            {"title": "Crypto Market Rally", "snippet": "Market showing strength", "source": "Decrypt"},
        ]
        return response

    @pytest.mark.asyncio
    async def test_execute_with_all_sources(
        self, tool, mock_telegram_tool, mock_grok_tool, mock_web_research_tool,
        mock_telegram_response, mock_grok_response, mock_news_response
    ):
        """测试使用所有数据源"""
        # Setup mocks
        mock_telegram_tool.execute = AsyncMock(return_value=mock_telegram_response)
        mock_grok_tool.execute = AsyncMock(return_value=mock_grok_response)
        mock_web_research_tool.execute = AsyncMock(return_value=mock_news_response)
        
        params = SentimentAggregatorInput(
            symbol="BTC",
            lookback_hours=24,
            sources=[SentimentSource.TELEGRAM, SentimentSource.TWITTER, SentimentSource.NEWS],
        )
        
        result = await tool.execute(params)
        
        # 验证返回类型
        assert isinstance(result, SentimentAggregatorOutput)
        assert result.symbol == "BTC"
        
        # 验证综合情绪
        assert result.overall_sentiment is not None
        assert 0 <= result.overall_sentiment.score <= 100
        assert result.overall_sentiment.label in ["very_bearish", "bearish", "neutral", "bullish", "very_bullish"]
        
        # 验证分源情绪
        assert len(result.source_breakdown) > 0

    @pytest.mark.asyncio
    async def test_execute_telegram_only(
        self, tool, mock_telegram_tool, mock_telegram_response
    ):
        """测试仅使用Telegram"""
        mock_telegram_tool.execute = AsyncMock(return_value=mock_telegram_response)
        
        params = SentimentAggregatorInput(
            symbol="ETH",
            lookback_hours=12,
            sources=[SentimentSource.TELEGRAM],
        )
        
        result = await tool.execute(params)
        
        assert isinstance(result, SentimentAggregatorOutput)
        assert "telegram" in result.source_breakdown

    @pytest.mark.asyncio
    async def test_execute_with_raw_samples(
        self, tool, mock_telegram_tool, mock_telegram_response
    ):
        """测试返回原始样本"""
        mock_telegram_tool.execute = AsyncMock(return_value=mock_telegram_response)
        
        params = SentimentAggregatorInput(
            symbol="BTC",
            lookback_hours=24,
            sources=[SentimentSource.TELEGRAM],
            include_raw_samples=True,
            sample_limit=5,
        )
        
        result = await tool.execute(params)
        
        assert result.raw_samples is not None
        assert "telegram" in result.raw_samples

    @pytest.mark.asyncio
    async def test_signals_generation(
        self, tool, mock_telegram_tool
    ):
        """测试信号生成"""
        # 模拟高度看涨的响应
        bullish_response = MagicMock()
        bullish_response.results = [
            {"text": "BTC to the moon! Bullish bullish bullish!"},
            {"text": "Pump pump pump!"},
            {"text": "Buy buy buy!"},
        ] * 10
        
        mock_telegram_tool.execute = AsyncMock(return_value=bullish_response)
        
        params = SentimentAggregatorInput(
            symbol="BTC",
            lookback_hours=24,
            sources=[SentimentSource.TELEGRAM],
        )
        
        result = await tool.execute(params)
        
        # 应该有信号生成
        # (信号取决于分数是否超过阈值)
        assert isinstance(result.signals, list)

    @pytest.mark.asyncio
    async def test_historical_sentiment(
        self, tool, mock_telegram_tool, mock_telegram_response
    ):
        """测试历史情绪趋势"""
        mock_telegram_tool.execute = AsyncMock(return_value=mock_telegram_response)
        
        params = SentimentAggregatorInput(
            symbol="BTC",
            lookback_hours=48,
            sources=[SentimentSource.TELEGRAM],
        )
        
        result = await tool.execute(params)
        
        # 应该有历史情绪数据
        assert isinstance(result.historical_sentiment, list)
        assert len(result.historical_sentiment) > 0

    @pytest.mark.asyncio
    async def test_no_sources_available(self):
        """测试无可用数据源"""
        tool = SentimentAggregatorTool(
            crypto_news_search_tool=None,
            grok_social_trace_tool=None,
            web_research_tool=None,
        )
        
        params = SentimentAggregatorInput(
            symbol="BTC",
            lookback_hours=24,
            sources=[SentimentSource.TELEGRAM],
        )
        
        result = await tool.execute(params)
        
        # 应该返回默认值和警告
        assert result.overall_sentiment.score == 50  # 中性
        assert len(result.warnings) > 0

    @pytest.mark.asyncio
    async def test_source_failure_handling(
        self, tool, mock_telegram_tool, mock_grok_tool
    ):
        """测试数据源失败处理"""
        # Telegram成功，Grok失败
        mock_telegram_response = MagicMock()
        mock_telegram_response.results = [{"text": "BTC looks good"}]
        mock_telegram_tool.execute = AsyncMock(return_value=mock_telegram_response)
        mock_grok_tool.execute = AsyncMock(side_effect=Exception("API Error"))
        
        params = SentimentAggregatorInput(
            symbol="BTC",
            lookback_hours=24,
            sources=[SentimentSource.TELEGRAM, SentimentSource.TWITTER],
        )
        
        result = await tool.execute(params)
        
        # 应该仍然返回结果，但有警告
        assert isinstance(result, SentimentAggregatorOutput)
        assert "telegram" in result.source_breakdown
        # Twitter失败应该生成警告
        assert any("twitter" in w.lower() for w in result.warnings)

    def test_input_validation(self):
        """测试输入验证"""
        # 正常输入
        params = SentimentAggregatorInput(symbol="btc", lookback_hours=24)
        # symbol应该转为大写
        assert params.symbol == "BTC"
        
        # lookback_hours边界测试
        with pytest.raises(Exception):
            SentimentAggregatorInput(symbol="BTC", lookback_hours=200)  # 超过168小时

    def test_analysis_period(
        self
    ):
        """测试分析周期计算"""
        params = SentimentAggregatorInput(
            symbol="BTC",
            lookback_hours=24,
        )
        assert params.lookback_hours == 24
