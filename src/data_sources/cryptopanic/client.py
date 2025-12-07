"""
CryptoPanic API客户端

提供加密货币新闻和情绪数据
API文档: https://cryptopanic.com/developers/api/
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.models import SourceMeta
from src.data_sources.base import BaseDataSource


class CryptoPanicClient(BaseDataSource):
    """CryptoPanic API客户端"""

    BASE_URL = "https://cryptopanic.com/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化CryptoPanic客户端

        Args:
            api_key: API密钥（可选，无密钥时使用公开数据）
        """
        super().__init__(
            name="cryptopanic",
            base_url=self.BASE_URL,
            timeout=15.0,
            requires_api_key=False,
        )
        self.api_key = api_key

    def _get_headers(self) -> Dict[str, str]:
        """构建请求头"""
        return {
            "accept": "application/json",
        }

    async def fetch_raw(self, endpoint: str, params: Optional[Dict] = None, base_url_override: Optional[str] = None) -> Any:
        """获取原始数据"""
        return await self._make_request("GET", endpoint, params, base_url_override)

    async def get_news(
        self,
        currencies: Optional[str] = None,
        kind: str = "news",
        filter_by: str = "hot",
        limit: int = 20,
    ) -> tuple[List[Dict], SourceMeta]:
        """
        获取新闻列表

        Args:
            currencies: 货币代码，如 BTC,ETH (逗号分隔)
            kind: 类型 (news/media/all)
            filter_by: 筛选 (rising/hot/bullish/bearish/important/saved/lol)
            limit: 数量限制

        Returns:
            (新闻列表, 元信息)
        """
        endpoint = "/posts/"
        params = {
            "filter": filter_by,
            "kind": kind,
        }

        if self.api_key:
            params["auth_token"] = self.api_key

        if currencies:
            params["currencies"] = currencies.upper()

        # CryptoPanic默认返回20条，我们通过多次请求获取更多
        # 但为了简化，这里只获取一页
        data, meta = await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="news",
            ttl_seconds=300,  # 5分钟缓存
        )

        # 限制返回数量
        if isinstance(data, dict) and "results" in data:
            data["results"] = data["results"][:limit]

        return data, meta

    def transform(self, raw_data: Any, data_type: str) -> Any:
        """转换原始数据为标准格式"""
        if data_type == "news":
            return self._transform_news(raw_data)
        return raw_data

    def _transform_news(self, data: Dict) -> List[Dict]:
        """转换新闻数据"""
        if not isinstance(data, dict) or "results" not in data:
            return []

        results = []
        for item in data.get("results", []):
            # 简单的情绪评分：基于投票
            votes = item.get("votes", {})
            positive = votes.get("positive", 0)
            negative = votes.get("negative", 0)
            total_votes = positive + negative

            # 计算情绪分数 (-1 到 1)
            if total_votes > 0:
                sentiment_score = (positive - negative) / total_votes
            else:
                # 基于kind字段的默认情绪
                kind = item.get("kind", "")
                if "bullish" in kind.lower():
                    sentiment_score = 0.5
                elif "bearish" in kind.lower():
                    sentiment_score = -0.5
                else:
                    sentiment_score = 0.0

            results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "source": item.get("source", {}).get("title", "Unknown"),
                    "published_at": item.get("published_at", datetime.utcnow().isoformat()),
                    "summary": None,  # CryptoPanic不提供摘要
                    "sentiment_score": sentiment_score,
                }
            )

        return results
