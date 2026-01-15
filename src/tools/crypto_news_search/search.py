"""
crypto_news_search 工具实现

提供加密新闻搜索功能。
"""
import time
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import structlog

from src.core.models import (
    SearchResult,
    SourceMeta,
    CryptoNewsSearchInput,
    CryptoNewsSearchOutput,
)
from src.data_sources.telegram_scraper import TelegramScraperClient

logger = structlog.get_logger()


class CryptoNewsSearchTool:
    """crypto_news_search 工具"""

    def __init__(self, telegram_scraper_client: Optional[TelegramScraperClient] = None):
        self.telegram_scraper_client = telegram_scraper_client
        logger.info(
            "crypto_news_search_tool_initialized",
            scraper_enabled=bool(telegram_scraper_client),
        )

    async def execute(self, params) -> CryptoNewsSearchOutput:
        if isinstance(params, dict):
            params = CryptoNewsSearchInput(**params)

        start = time.time()

        warnings: List[str] = []
        if not params.query and not params.symbol:
            warnings.append("未提供 query 或 symbol，将返回最新消息（受 limit 限制）")

        start_window = self._parse_time_range(params.time_range)
        start_iso = params.start_time
        if not start_iso and start_window:
            start_iso = start_window.replace(microsecond=0).isoformat() + "Z"

        results: List[SearchResult] = []
        source_meta: List[SourceMeta] = []

        if not self.telegram_scraper_client:
            warnings.append("Telegram scraper 未初始化（检查 TELEGRAM_SCRAPER_URL 配置）")
        else:
            data, meta = await self.telegram_scraper_client.search_messages(
                keyword=params.query,
                symbol=params.symbol,
                limit=params.limit,
                sort_by=params.sort_by,
                start_time=start_iso,
            )
            results = [SearchResult(**item) for item in data]
            source_meta = [meta]

        elapsed = time.time() - start
        logger.info(
            "crypto_news_search_execute_complete",
            query=params.query,
            symbol=params.symbol,
            results_count=len(results),
            elapsed_ms=round(elapsed * 1000, 2),
        )

        return CryptoNewsSearchOutput(
            query=params.query,
            symbol=params.symbol,
            results=results,
            total_results=len(results),
            source_meta=source_meta,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )

    def _parse_time_range(self, time_range: Optional[str]) -> Optional[datetime]:
        if not time_range:
            return None

        tr = time_range.lower().strip()
        if tr.startswith("past_"):
            tr = tr[len("past_") :]

        now = datetime.utcnow()

        if tr.endswith("h") and tr[:-1].isdigit():
            return now - timedelta(hours=int(tr[:-1]))
        if tr.endswith("d") and tr[:-1].isdigit():
            return now - timedelta(days=int(tr[:-1]))

        if "day" in tr:
            return now - timedelta(days=1)
        if "week" in tr or "7d" in tr:
            return now - timedelta(weeks=1)
        if "month" in tr or "30d" in tr:
            return now - timedelta(days=30)
        if "year" in tr or "365" in tr:
            return now - timedelta(days=365)

        return None
