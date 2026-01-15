"""
Telegram Scraper API客户端

提供从Elasticsearch获取Telegram数据
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

from src.core.models import SourceMeta
from src.data_sources.base import BaseDataSource

logger = structlog.get_logger()


class TelegramScraperClient(BaseDataSource):
    """Telegram Scraper客户端（通过 tel2es FastAPI）"""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 15.0,
        verify_ssl: bool = False,  # 默认禁用 SSL 验证（支持自签名证书）
    ):
        """
        初始化Telegram Scraper客户端

        Args:
            base_url: tel2es FastAPI 服务 URL
            timeout: 请求超时时间（秒）
            verify_ssl: 是否验证 SSL 证书（默认 False，支持自签名证书）
        """
        super().__init__(
            name="telegram_scraper",
            base_url=base_url,
            timeout=timeout,
            requires_api_key=False,
        )
        self.verify_ssl = verify_ssl
        logger.info(
            "telegram_scraper_client_initialized",
            base_url=base_url,
            verify_ssl=verify_ssl,
        )

    def _get_headers(self) -> Dict[str, str]:
        """构建请求头"""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @property
    def client(self):
        """获取HTTP客户端（支持禁用 SSL 验证）"""
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._get_headers(),
                timeout=self.timeout,
                verify=self.verify_ssl,  # 支持自签名证书
                follow_redirects=True,
            )
        return self._client

    async def fetch_raw(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        base_url_override: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """获取原始数据"""
        return await self._make_request(
            "GET",
            endpoint,
            params=params,
            base_url_override=base_url_override,
            headers=headers,
        )

    @staticmethod
    def _normalize_iso(dt: Optional[str]) -> Optional[str]:
        if not dt:
            return None
        normalized = dt.strip()
        if normalized.endswith("Z"):
            # tel2es uses datetime.fromisoformat, which doesn't accept trailing "Z"
            return normalized[:-1] + "+00:00"
        return normalized

    async def search_messages(
        self,
        keyword: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
        sort_by: str = "timestamp",
        start_time: Optional[str] = None,
    ) -> tuple[list[dict], SourceMeta]:
        """
        搜索Telegram数据

        Args:
            keyword: 搜索关键词
            symbol: 币种符号（如 BTC, ETH）
            limit: 返回结果数量限制（默认50）
            sort_by: 排序字段（timestamp/score）

        Returns:
            (消息列表, 元信息)
        """
        query_term = keyword or symbol
        start_time = self._normalize_iso(start_time)

        # tel2es:
        # - /search: requires keywords, sorts by score
        # - /latest: returns newest messages
        if query_term:
            endpoint = "/search"
            params = {
                "keywords": query_term,
                "start_time": start_time,
                "limit": min(limit, 100),
                "offset": 0,
            }
            data_type = "search"
        else:
            endpoint = "/latest"
            params = {
                "start_time": start_time,
                "limit": min(limit, 100),
                "offset": 0,
            }
            data_type = "latest"

        if sort_by not in {"timestamp", "score"}:
            sort_by = "timestamp"

        # 执行搜索
        try:
            data, meta = await self.fetch(
                endpoint=endpoint,
                params={k: v for k, v in params.items() if v is not None},
                data_type=data_type,
                ttl_seconds=60,  # 1分钟缓存
            )
            return data, meta
        except Exception as e:
            logger.error(
                "crypto_news_search_failed",
                error=str(e),
                keyword=keyword,
                symbol=symbol,
            )
            raise

    def transform(self, raw_data: Any, data_type: str) -> Any:
        """转换原始数据为标准格式"""
        if data_type in {"search", "latest"}:
            return self._transform_api_response(raw_data)
        return raw_data

    def _transform_api_response(self, data: Dict) -> List[Dict]:
        if not isinstance(data, dict):
            return []

        hits = data.get("hits", [])
        if not isinstance(hits, list):
            return []

        results: List[Dict] = []
        for item in hits:
            if not isinstance(item, dict):
                continue

            text = item.get("text", "") or ""
            chat_title = item.get("chat_title") or "Unknown Chat"
            timestamp = item.get("timestamp") or datetime.utcnow().isoformat()

            if len(text) > 100:
                title = f"{chat_title}: {text[:100]}..."
            else:
                title = f"{chat_title}: {text}"

            results.append(
                {
                    "title": title,
                    "url": "",
                    "snippet": text,
                    "source": f"Telegram - {chat_title}",
                    "published_at": timestamp if isinstance(timestamp, str) else str(timestamp),
                    "relevance_score": item.get("score"),
                    "telegram_meta": {
                        "message_id": item.get("message_id"),
                        "chat_id": item.get("chat_id"),
                        "chat_title": chat_title,
                        "chat_type": item.get("chat_type"),
                        "user_id": item.get("user_id"),
                        "username": item.get("username"),
                        "first_name": item.get("first_name"),
                        "timestamp": timestamp if isinstance(timestamp, str) else str(timestamp),
                    },
                }
            )

        return results
