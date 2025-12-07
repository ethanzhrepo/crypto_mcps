"""
Twitter API v2客户端

提供推特数据和社交情绪分析
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.core.models import SourceMeta
from src.data_sources.base import BaseDataSource
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TwitterClient(BaseDataSource):
    """Twitter API v2客户端"""

    def __init__(self, bearer_token: Optional[str] = None):
        """
        初始化Twitter客户端

        Args:
            bearer_token: Twitter API Bearer Token（必需）
        """
        base_url = "https://api.twitter.com/2"
        super().__init__(
            name="twitter",
            base_url=base_url,
            timeout=10.0,
            requires_api_key=True,
        )
        self.bearer_token = bearer_token

    def _get_headers(self) -> Dict[str, str]:
        """构建请求头"""
        if not self.bearer_token:
            raise ValueError("Twitter API bearer token is required")

        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
        }

    async def fetch_raw(self, endpoint: str, params: Optional[Dict] = None, base_url_override: Optional[str] = None) -> Any:
        """获取原始数据"""
        return await self._make_request("GET", endpoint, params, base_url_override)

    def transform(self, raw_data: Any, data_type: str) -> Dict[str, Any]:
        """
        转换原始数据为标准格式

        Args:
            raw_data: Twitter API原始响应
            data_type: 数据类型

        Returns:
            标准化数据字典
        """
        if data_type == "tweet":
            return self._transform_tweet(raw_data)
        elif data_type == "user":
            return self._transform_user(raw_data)
        else:
            return raw_data

    # ==================== 公共API方法 ====================

    async def search_recent_tweets(
        self,
        query: str,
        max_results: int = 10,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> tuple[List[Dict], SourceMeta]:
        """
        搜索最近的推文（过去7天）

        Args:
            query: 搜索查询（支持Twitter搜索运算符）
            max_results: 返回结果数（10-100）
            start_time: 开始时间（ISO 8601格式）
            end_time: 结束时间（ISO 8601格式）

        Returns:
            (推文列表, SourceMeta)
        """
        endpoint = "/tweets/search/recent"
        params = {
            "query": query,
            "max_results": min(max_results, 100),
            "tweet.fields": "created_at,public_metrics,author_id,lang",
            "expansions": "author_id",
            "user.fields": "username,verified,public_metrics",
        }

        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        raw_data = await self.fetch_raw(endpoint, params)

        meta = SourceMeta(
            provider="twitter",
            endpoint=endpoint,
            fetched_at=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=300,  # 5分钟缓存
            cache_hit=False,
        )

        # 转换推文数据
        tweets = raw_data.get("data", [])
        users = {u["id"]: u for u in raw_data.get("includes", {}).get("users", [])}

        transformed_tweets = []
        for tweet in tweets:
            transformed = self._transform_tweet(tweet)
            # 添加用户信息
            author_id = tweet.get("author_id")
            if author_id and author_id in users:
                transformed["author"] = self._transform_user(users[author_id])
            transformed_tweets.append(transformed)

        return transformed_tweets, meta

    async def get_tweet_counts(
        self,
        query: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        granularity: str = "hour",
    ) -> tuple[Dict, SourceMeta]:
        """
        获取推文数量统计

        Args:
            query: 搜索查询
            start_time: 开始时间
            end_time: 结束时间
            granularity: 时间粒度（minute, hour, day）

        Returns:
            (统计数据, SourceMeta)
        """
        endpoint = "/tweets/counts/recent"
        params = {
            "query": query,
            "granularity": granularity,
        }

        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        raw_data = await self.fetch_raw(endpoint, params)

        meta = SourceMeta(
            provider="twitter",
            endpoint=endpoint,
            fetched_at=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=300,
            cache_hit=False,
        )

        counts_data = raw_data.get("data", [])
        total_count = raw_data.get("meta", {}).get("total_tweet_count", 0)

        return {
            "query": query,
            "total_count": total_count,
            "granularity": granularity,
            "counts": counts_data,
        }, meta

    async def get_user_by_username(
        self,
        username: str,
    ) -> tuple[Dict, SourceMeta]:
        """
        根据用户名获取用户信息

        Args:
            username: Twitter用户名（不含@）

        Returns:
            (用户信息, SourceMeta)
        """
        endpoint = f"/users/by/username/{username}"
        params = {
            "user.fields": "created_at,description,public_metrics,verified",
        }

        raw_data = await self.fetch_raw(endpoint, params)

        meta = SourceMeta(
            provider="twitter",
            endpoint=endpoint,
            fetched_at=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=3600,  # 1小时缓存
            cache_hit=False,
        )

        user = raw_data.get("data", {})
        return self._transform_user(user), meta

    async def get_user_tweets(
        self,
        user_id: str,
        max_results: int = 10,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> tuple[List[Dict], SourceMeta]:
        """
        获取用户推文

        Args:
            user_id: 用户ID
            max_results: 返回结果数
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            (推文列表, SourceMeta)
        """
        endpoint = f"/users/{user_id}/tweets"
        params = {
            "max_results": min(max_results, 100),
            "tweet.fields": "created_at,public_metrics,lang",
        }

        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        raw_data = await self.fetch_raw(endpoint, params)

        meta = SourceMeta(
            provider="twitter",
            endpoint=endpoint,
            fetched_at=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=300,
            cache_hit=False,
        )

        tweets = raw_data.get("data", [])
        return [self._transform_tweet(t) for t in tweets], meta

    async def get_crypto_sentiment(
        self,
        symbol: str,
        hours: int = 24,
    ) -> tuple[Dict, SourceMeta]:
        """
        获取加密货币相关推文情绪

        Args:
            symbol: 币种符号（如BTC, ETH）
            hours: 回溯小时数

        Returns:
            (情绪分析数据, SourceMeta)
        """
        # 构建查询（使用常见hashtags和cashtags）
        query = f"${symbol} OR #{symbol} OR #{symbol}crypto -is:retweet lang:en"

        # 计算时间范围
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)

        # 获取推文
        tweets, meta = await self.search_recent_tweets(
            query=query,
            max_results=100,
            start_time=start_time.isoformat() + "Z",
            end_time=end_time.isoformat() + "Z",
        )

        # 获取推文数量趋势
        counts, _ = await self.get_tweet_counts(
            query=query,
            start_time=start_time.isoformat() + "Z",
            end_time=end_time.isoformat() + "Z",
            granularity="hour",
        )

        # 计算情绪指标
        sentiment_metrics = self._calculate_sentiment_metrics(tweets)

        return {
            "symbol": symbol,
            "query": query,
            "time_range_hours": hours,
            "tweet_count": len(tweets),
            "total_count": counts.get("total_count", 0),
            "metrics": sentiment_metrics,
            "top_tweets": tweets[:10],  # 前10条推文
            "hourly_counts": counts.get("counts", []),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }, meta

    # ==================== 数据转换方法 ====================

    def _transform_tweet(self, data: Dict) -> Dict:
        """转换推文数据"""
        metrics = data.get("public_metrics", {})

        return {
            "id": data.get("id"),
            "text": data.get("text"),
            "created_at": data.get("created_at"),
            "author_id": data.get("author_id"),
            "lang": data.get("lang"),
            "retweet_count": metrics.get("retweet_count", 0),
            "reply_count": metrics.get("reply_count", 0),
            "like_count": metrics.get("like_count", 0),
            "quote_count": metrics.get("quote_count", 0),
            "impression_count": metrics.get("impression_count", 0),
        }

    def _transform_user(self, data: Dict) -> Dict:
        """转换用户数据"""
        metrics = data.get("public_metrics", {})

        return {
            "id": data.get("id"),
            "username": data.get("username"),
            "name": data.get("name"),
            "verified": data.get("verified", False),
            "description": data.get("description"),
            "created_at": data.get("created_at"),
            "followers_count": metrics.get("followers_count", 0),
            "following_count": metrics.get("following_count", 0),
            "tweet_count": metrics.get("tweet_count", 0),
        }

    def _calculate_sentiment_metrics(self, tweets: List[Dict]) -> Dict:
        """
        计算情绪指标

        Args:
            tweets: 推文列表

        Returns:
            情绪指标字典
        """
        if not tweets:
            return {
                "avg_likes": 0,
                "avg_retweets": 0,
                "avg_replies": 0,
                "engagement_rate": 0,
                "verified_ratio": 0,
                "sentiment_score": 0,
            }

        total_likes = sum(t.get("like_count", 0) for t in tweets)
        total_retweets = sum(t.get("retweet_count", 0) for t in tweets)
        total_replies = sum(t.get("reply_count", 0) for t in tweets)
        total_engagement = total_likes + total_retweets + total_replies

        verified_count = sum(
            1 for t in tweets
            if t.get("author", {}).get("verified", False)
        )

        # 简单的情绪评分：基于互动率
        engagement_rate = total_engagement / len(tweets) if tweets else 0

        # 归一化情绪分数（0-100）
        # 高互动 = 正面情绪（简化假设）
        sentiment_score = min(100, engagement_rate / 10)

        return {
            "avg_likes": total_likes / len(tweets),
            "avg_retweets": total_retweets / len(tweets),
            "avg_replies": total_replies / len(tweets),
            "engagement_rate": engagement_rate,
            "verified_ratio": (verified_count / len(tweets)) * 100,
            "sentiment_score": sentiment_score,
        }
