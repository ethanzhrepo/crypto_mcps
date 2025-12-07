"""
Telegram Scraper API客户端

提供从Elasticsearch获取Telegram消息数据
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import structlog

from src.core.models import SourceMeta
from src.data_sources.base import BaseDataSource

logger = structlog.get_logger()


class TelegramScraperClient(BaseDataSource):
    """Telegram Scraper客户端（通过Elasticsearch API）"""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        index_name: str = "telegram_messages",
        timeout: float = 15.0,
    ):
        """
        初始化Telegram Scraper客户端

        Args:
            base_url: Elasticsearch基础URL
            index_name: 索引名称
            timeout: 请求超时时间（秒）
        """
        super().__init__(
            name="telegram_scraper",
            base_url=base_url,
            timeout=timeout,
            requires_api_key=False,
        )
        self.index_name = index_name
        logger.info(
            "telegram_scraper_client_initialized",
            base_url=base_url,
            index_name=index_name,
        )

    def _get_headers(self) -> Dict[str, str]:
        """构建请求头"""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def fetch_raw(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        base_url_override: Optional[str] = None,
    ) -> Any:
        """获取原始数据"""
        # 对于 POST 请求，params 作为 JSON body
        return await self._make_request(
            "POST", endpoint, json_body=params, base_url_override=base_url_override
        )

    async def search_messages(
        self,
        keyword: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
        sort_by: str = "timestamp",
        start_time: Optional[str] = None,
    ) -> Tuple[List[Dict], SourceMeta]:
        """
        搜索Telegram消息

        Args:
            keyword: 搜索关键词
            symbol: 币种符号（如 BTC, ETH）
            limit: 返回结果数量限制（默认50）
            sort_by: 排序字段（timestamp/score）

        Returns:
            (消息列表, 元信息)
        """
        endpoint = f"/{self.index_name}/_search"

        # 构建查询
        query_term = keyword or symbol
        if not query_term:
            # 如果没有指定关键词，返回最新消息
            search_query = {"match_all": {}}
        else:
            # 多字段搜索
            search_query = {
                "multi_match": {
                    "query": query_term,
                    "fields": ["text", "channel_title", "sender_name"],
                }
            }

        if start_time:
            search_query = {
                "bool": {
                    "must": search_query,
                    "filter": [
                        {
                            "range": {
                                "timestamp": {
                                    "gte": start_time,
                                }
                            }
                        }
                    ],
                }
            }

        # 构建排序
        if sort_by == "timestamp":
            sort_config = [{"timestamp": {"order": "desc"}}]
        else:
            # 按相关性和时间排序
            sort_config = [
                {"_score": {"order": "desc"}},
                {"timestamp": {"order": "desc"}},
            ]

        # 构建请求体
        body = {
            "query": search_query,
            "size": limit,
            "sort": sort_config,
        }

        logger.debug(
            "telegram_search_query",
            keyword=keyword,
            symbol=symbol,
            limit=limit,
            query=search_query,
        )

        # 执行搜索
        try:
            data, meta = await self.fetch(
                endpoint=endpoint,
                params=body,
                data_type="messages",
                ttl_seconds=60,  # 1分钟缓存
            )
            return data, meta
        except Exception as e:
            logger.error(
                "telegram_search_failed",
                error=str(e),
                keyword=keyword,
                symbol=symbol,
            )
            raise

    def transform(self, raw_data: Any, data_type: str) -> Any:
        """转换原始数据为标准格式"""
        if data_type == "messages":
            return self._transform_messages(raw_data)
        return raw_data

    def _transform_messages(self, data: Dict) -> List[Dict]:
        """
        转换Telegram消息数据为SearchResult格式

        Args:
            data: Elasticsearch返回的原始数据

        Returns:
            标准化的消息列表
        """
        if not isinstance(data, dict) or "hits" not in data:
            logger.warning(
                "invalid_telegram_response",
                data_keys=list(data.keys()) if isinstance(data, dict) else None,
            )
            return []

        hits = data.get("hits", {}).get("hits", [])
        results = []

        for hit in hits:
            source = hit.get("_source", {})

            # 提取消息内容
            text = source.get("text", "")
            channel_title = source.get("channel_title", "Unknown Channel")
            sender_name = source.get("sender_name", "")
            timestamp = source.get("timestamp", datetime.utcnow().isoformat())
            message_id = source.get("message_id", hit.get("_id", ""))
            channel_username = source.get("channel_username", "")

            # 构建消息URL（如果有channel_username）
            url = ""
            if channel_username:
                url = f"https://t.me/{channel_username}/{message_id}"

            # 构建标题（取前100字符）
            if len(text) > 100:
                title = f"{channel_title}: {text[:100]}..."
            else:
                title = f"{channel_title}: {text}"

            # 转换为标准格式
            results.append(
                {
                    "title": title,
                    "url": url,
                    "snippet": text,
                    "source": f"Telegram - {channel_title}",
                    "published_at": timestamp,
                    "relevance_score": hit.get("_score"),
                    # 额外的Telegram特定字段
                    "telegram_meta": {
                        "message_id": message_id,
                        "channel_username": channel_username,
                        "sender_name": sender_name,
                        "views": source.get("views", 0),
                        "forwards": source.get("forwards", 0),
                        "replies": source.get("replies", 0),
                        "timestamp": timestamp,
                    },
                }
            )

        logger.info(
            "telegram_messages_transformed",
            total_hits=data.get("hits", {}).get("total", {}).get("value", 0),
            returned=len(results),
        )

        return results
