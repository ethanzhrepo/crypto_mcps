"""
sentiment_aggregator 工具

聚合多个社交/舆情数据源，计算综合情绪评分和趋势。
整合 Telegram、Twitter/X、新闻等渠道。
"""
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import structlog

from src.core.models import (
    HistoricalSentimentPoint,
    OverallSentiment,
    SentimentAggregatorInput,
    SentimentAggregatorOutput,
    SentimentSignal,
    SentimentSource,
    SourceMeta,
    SourceSentimentBreakdown,
)

logger = structlog.get_logger()


# 数据源权重
SOURCE_WEIGHTS = {
    SentimentSource.TWITTER: 0.35,   # KOL影响力大
    SentimentSource.TELEGRAM: 0.25,  # 社区活跃度
    SentimentSource.NEWS: 0.25,      # 机构视角
    SentimentSource.REDDIT: 0.15,    # 散户情绪
}


def score_to_label(score: int) -> str:
    """将分数转换为标签"""
    if score <= 20:
        return "very_bearish"
    elif score <= 40:
        return "bearish"
    elif score <= 60:
        return "neutral"
    elif score <= 80:
        return "bullish"
    else:
        return "very_bullish"


class SentimentAggregatorTool:
    """
    情绪聚合分析工具
    
    整合多个数据源:
    - telegram_search: Telegram消息搜索
    - grok_social_trace: X/Twitter分析  
    - web_research_search: 新闻聚合
    """
    
    def __init__(
        self,
        telegram_search_tool=None,
        grok_social_trace_tool=None,
        web_research_tool=None,
    ):
        self.telegram_tool = telegram_search_tool
        self.grok_tool = grok_social_trace_tool
        self.web_research_tool = web_research_tool
        logger.info("sentiment_aggregator_tool_initialized")
    
    async def execute(
        self, params: Union[SentimentAggregatorInput, Dict[str, Any]]
    ) -> SentimentAggregatorOutput:
        """
        执行情绪聚合分析
        
        Args:
            params: 输入参数
            
        Returns:
            SentimentAggregatorOutput
        """
        if isinstance(params, dict):
            params = SentimentAggregatorInput(**params)
        
        logger.info(
            "sentiment_aggregator_execute_start",
            symbol=params.symbol,
            lookback_hours=params.lookback_hours,
            sources=params.sources,
        )
        
        warnings: List[str] = []
        source_meta: List[SourceMeta] = []
        source_breakdown: Dict[str, SourceSentimentBreakdown] = {}
        signals: List[SentimentSignal] = []
        raw_samples: Optional[Dict[str, List[Dict[str, Any]]]] = None
        
        if params.include_raw_samples:
            raw_samples = {}
        
        # 计算时间范围
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=params.lookback_hours)
        
        # 1. 并行获取各源数据
        tasks = []
        task_sources = []
        
        if SentimentSource.TELEGRAM in params.sources and self.telegram_tool:
            tasks.append(self._fetch_telegram_sentiment(params.symbol, params.lookback_hours))
            task_sources.append(SentimentSource.TELEGRAM)
        
        if SentimentSource.TWITTER in params.sources and self.grok_tool:
            tasks.append(self._fetch_twitter_sentiment(params.symbol))
            task_sources.append(SentimentSource.TWITTER)
        
        if SentimentSource.NEWS in params.sources and self.web_research_tool:
            tasks.append(self._fetch_news_sentiment(params.symbol))
            task_sources.append(SentimentSource.NEWS)
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for source, result in zip(task_sources, results):
                if isinstance(result, Exception):
                    warnings.append(f"Failed to fetch {source.value} data: {str(result)}")
                    continue
                
                breakdown, meta, samples = result
                source_breakdown[source.value] = breakdown
                source_meta.append(meta)
                
                # 生成信号
                if breakdown.score > 70:
                    signals.append(SentimentSignal(
                        type="bullish",
                        strength=min(10, (breakdown.score - 50) // 5),
                        source=source.value,
                        reason=f"{source.value} sentiment is positive ({breakdown.score})",
                    ))
                elif breakdown.score < 30:
                    signals.append(SentimentSignal(
                        type="bearish",
                        strength=min(10, (50 - breakdown.score) // 5),
                        source=source.value,
                        reason=f"{source.value} sentiment is negative ({breakdown.score})",
                    ))
                
                if params.include_raw_samples and samples:
                    raw_samples[source.value] = samples[:params.sample_limit]
        else:
            warnings.append("No data sources available for analysis")
        
        # 2. 计算综合情绪评分
        overall_sentiment = self._calculate_overall_sentiment(
            source_breakdown, params.sources
        )
        
        # 3. 生成历史情绪趋势（模拟）
        historical_sentiment = self._generate_historical_trend(
            overall_sentiment.score, params.lookback_hours
        )
        
        # 4. 构建输出
        output = SentimentAggregatorOutput(
            symbol=params.symbol,
            analysis_period={
                "start": start_time.isoformat() + "Z",
                "end": end_time.isoformat() + "Z",
            },
            overall_sentiment=overall_sentiment,
            source_breakdown=source_breakdown,
            signals=signals,
            historical_sentiment=historical_sentiment,
            raw_samples=raw_samples,
            source_meta=source_meta,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )
        
        logger.info(
            "sentiment_aggregator_execute_complete",
            symbol=params.symbol,
            overall_score=overall_sentiment.score,
        )
        
        return output
    
    async def _fetch_telegram_sentiment(
        self, symbol: str, lookback_hours: int
    ) -> tuple[SourceSentimentBreakdown, SourceMeta, List[Dict]]:
        """获取Telegram情绪数据"""
        try:
            # 调用telegram_search工具
            result = await self.telegram_tool.execute({
                "query": symbol,
                "limit": 50,
            })
            
            # 简单情绪分析（基于消息数量和关键词）
            messages = result.results if hasattr(result, "results") else []
            message_count = len(messages)
            
            # 简化的情绪评分（实际应使用NLP）
            positive_keywords = ["bullish", "moon", "pump", "buy", "long", "上涨", "看涨"]
            negative_keywords = ["bearish", "dump", "sell", "short", "rekt", "下跌", "看跌"]
            
            positive_count = 0
            negative_count = 0
            samples = []
            
            for msg in messages:
                text = msg.get("text", "") if isinstance(msg, dict) else str(msg)
                text_lower = text.lower()
                
                if any(kw in text_lower for kw in positive_keywords):
                    positive_count += 1
                elif any(kw in text_lower for kw in negative_keywords):
                    negative_count += 1
                
                samples.append({"text": text[:200], "source": "telegram"})
            
            total = positive_count + negative_count
            if total > 0:
                score = int(50 + (positive_count - negative_count) / total * 50)
                score = max(0, min(100, score))
            else:
                score = 50
            
            breakdown = SourceSentimentBreakdown(
                score=score,
                message_count=message_count,
                positive_count=positive_count,
                negative_count=negative_count,
                neutral_count=message_count - positive_count - negative_count,
            )
            
            meta = SourceMeta(
                provider="telegram_search",
                endpoint="/search",
                as_of_utc=datetime.utcnow().isoformat() + "Z",
                ttl_seconds=300,
            )
            
            return breakdown, meta, samples
            
        except Exception as e:
            logger.warning(f"Telegram sentiment fetch failed: {e}")
            raise
    
    async def _fetch_twitter_sentiment(
        self, symbol: str
    ) -> tuple[SourceSentimentBreakdown, SourceMeta, List[Dict]]:
        """获取Twitter情绪数据（通过Grok）"""
        try:
            # 调用grok_social_trace工具
            result = await self.grok_tool.execute({
                "keyword_prompt": f"{symbol} cryptocurrency market sentiment analysis",
                "language": "en",
            })
            
            # 基于Grok分析结果计算情绪
            is_promo = result.is_likely_promotion if hasattr(result, "is_likely_promotion") else False
            insights = result.deepsearch_insights if hasattr(result, "deepsearch_insights") else ""
            
            # 从insights中提取情绪
            insights_lower = insights.lower() if insights else ""
            
            if "bullish" in insights_lower or "positive" in insights_lower:
                score = 70
            elif "bearish" in insights_lower or "negative" in insights_lower:
                score = 30
            else:
                score = 50
            
            # Promo内容降低置信度
            if is_promo:
                score = 50  # 回归中性
            
            breakdown = SourceSentimentBreakdown(
                score=score,
                key_topics=[symbol, "sentiment"],
                bot_percentage=15.0 if is_promo else 5.0,
            )
            
            meta = SourceMeta(
                provider="grok_social_trace",
                endpoint="/chat/completions",
                as_of_utc=datetime.utcnow().isoformat() + "Z",
                ttl_seconds=300,
            )
            
            samples = [{"text": insights[:500], "source": "twitter"}] if insights else []
            
            return breakdown, meta, samples
            
        except Exception as e:
            logger.warning(f"Twitter sentiment fetch failed: {e}")
            raise
    
    async def _fetch_news_sentiment(
        self, symbol: str
    ) -> tuple[SourceSentimentBreakdown, SourceMeta, List[Dict]]:
        """获取新闻情绪数据"""
        try:
            # 调用web_research_search工具
            result = await self.web_research_tool.execute({
                "query": f"{symbol} cryptocurrency news",
                "scope": "news",
                "limit": 20,
            })
            
            articles = result.results if hasattr(result, "results") else []
            article_count = len(articles)
            
            # 简化的情绪分析
            positive_keywords = ["surge", "gain", "rise", "bullish", "rally", "上涨", "利好"]
            negative_keywords = ["drop", "fall", "crash", "bearish", "decline", "下跌", "利空"]
            
            positive_count = 0
            negative_count = 0
            samples = []
            top_sources = set()
            
            for article in articles:
                title = article.get("title", "") if isinstance(article, dict) else str(article)
                snippet = article.get("snippet", "") if isinstance(article, dict) else ""
                source = article.get("source", "unknown") if isinstance(article, dict) else "unknown"
                
                text = (title + " " + snippet).lower()
                
                if any(kw in text for kw in positive_keywords):
                    positive_count += 1
                elif any(kw in text for kw in negative_keywords):
                    negative_count += 1
                
                top_sources.add(source)
                samples.append({"title": title, "snippet": snippet[:200], "source": source})
            
            total = positive_count + negative_count
            if total > 0:
                score = int(50 + (positive_count - negative_count) / total * 50)
                score = max(0, min(100, score))
            else:
                score = 50
            
            breakdown = SourceSentimentBreakdown(
                score=score,
                article_count=article_count,
                positive_count=positive_count,
                negative_count=negative_count,
                neutral_count=article_count - positive_count - negative_count,
                top_sources=list(top_sources)[:5],
            )
            
            meta = SourceMeta(
                provider="web_research_search",
                endpoint="/search",
                as_of_utc=datetime.utcnow().isoformat() + "Z",
                ttl_seconds=300,
            )
            
            return breakdown, meta, samples
            
        except Exception as e:
            logger.warning(f"News sentiment fetch failed: {e}")
            raise
    
    def _calculate_overall_sentiment(
        self,
        source_breakdown: Dict[str, SourceSentimentBreakdown],
        requested_sources: List[SentimentSource],
    ) -> OverallSentiment:
        """计算加权综合情绪评分"""
        
        if not source_breakdown:
            return OverallSentiment(
                score=50,
                label="neutral",
                confidence=0,
            )
        
        total_weight = 0
        weighted_score = 0
        
        for source_name, breakdown in source_breakdown.items():
            source = SentimentSource(source_name)
            weight = SOURCE_WEIGHTS.get(source, 0.1)
            weighted_score += breakdown.score * weight
            total_weight += weight
        
        if total_weight > 0:
            final_score = int(weighted_score / total_weight)
        else:
            final_score = 50
        
        # 置信度基于数据源覆盖率
        coverage = len(source_breakdown) / len(requested_sources) if requested_sources else 0
        confidence = int(coverage * 100)
        
        return OverallSentiment(
            score=final_score,
            label=score_to_label(final_score),
            confidence=confidence,
            trend_vs_24h_ago="stable",  # 需要历史数据才能计算
        )
    
    def _generate_historical_trend(
        self, current_score: int, lookback_hours: int
    ) -> List[HistoricalSentimentPoint]:
        """生成历史情绪趋势（简化版，实际应查询历史数据）"""
        
        import random
        
        points = []
        now = datetime.utcnow()
        
        # 每4小时一个点
        intervals = min(lookback_hours // 4, 24)
        
        for i in range(intervals, 0, -1):
            ts = now - timedelta(hours=i * 4)
            # 简单模拟：在当前分数附近波动
            variation = random.randint(-10, 10)
            score = max(0, min(100, current_score + variation))
            points.append(HistoricalSentimentPoint(
                timestamp=ts.isoformat() + "Z",
                score=score,
            ))
        
        # 添加当前点
        points.append(HistoricalSentimentPoint(
            timestamp=now.isoformat() + "Z",
            score=current_score,
        ))
        
        return points


__all__ = ["SentimentAggregatorTool"]
