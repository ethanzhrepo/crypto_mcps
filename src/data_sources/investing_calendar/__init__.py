"""
Investing.com 财经日历爬虫

提供宏观财经事件日历：
- 央行决议（利率决定、货币政策）
- 经济数据发布（CPI、非农、GDP等）
- 财报季关键事件
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

from src.core.models import SourceMeta
from src.core.source_meta import SourceMetaBuilder
from src.data_sources.base import BaseDataSource


class InvestingCalendarClient(BaseDataSource):
    """Investing.com 财经日历客户端"""

    BASE_URL = "https://www.investing.com"

    def __init__(self, redis_client: Optional[Any] = None):
        """初始化Investing.com日历客户端（无需API key）"""
        super().__init__(
            name="investing_calendar",
            base_url=self.BASE_URL,
            timeout=30.0,  # 增加timeout以适应浏览器
            requires_api_key=False,
        )
        # Redis缓存客户端（可选）
        self.redis_client = redis_client

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头（模拟浏览器）"""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.investing.com/",
        }

    async def fetch_raw(
        self, endpoint: str, params: Optional[Dict] = None, base_url_override: Optional[str] = None
    ) -> Any:
        """
        使用Playwright无头浏览器获取HTML（处理JavaScript渲染）

        Args:
            endpoint: 路径
            params: 查询参数
            base_url_override: 可选的基础URL覆盖

        Returns:
            渲染后的HTML内容
        """
        from playwright.async_api import async_playwright
        from src.utils.logger import get_logger

        logger = get_logger(__name__)

        base = base_url_override or self.base_url
        url = f"{base}{endpoint}"

        # 添加查询参数到URL
        if params:
            from urllib.parse import urlencode
            url = f"{url}?{urlencode(params)}"

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage']  # Docker友好
                )

                page = await browser.new_page()

                # 设置User-Agent
                await page.set_extra_http_headers(self._get_headers())

                # 导航到页面 - 使用domcontentloaded而非networkidle（更快，避免timeout）
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)

                # 等待经济日历表格加载
                await page.wait_for_selector(
                    "table#economicCalendarData, table.genTbl",
                    timeout=10000,
                )

                # 等待事件行加载（关键：等待JavaScript渲染完成）
                await page.wait_for_selector(
                    "tr.js-event-item, tr[data-event-datetime]",
                    timeout=8000,
                    state="attached"
                )

                # 获取渲染后的HTML
                html = await page.content()

                await browser.close()

                logger.info(
                    "calendar_fetched_with_playwright",
                    url=url,
                    html_length=len(html),
                )

                return html

        except Exception as e:
            logger.error(
                "playwright_fetch_failed",
                url=url,
                error=str(e),
            )
            raise

    def transform(self, raw_data: Any, data_type: str) -> Dict[str, Any]:
        """
        转换原始HTML为结构化数据

        Args:
            raw_data: 原始HTML
            data_type: 数据类型

        Returns:
            结构化数据
        """
        if data_type == "calendar":
            return self._parse_calendar(raw_data)
        return {"error": "Unknown data type"}

    def _parse_calendar(self, html: str) -> Dict[str, Any]:
        """
        解析财经日历HTML

        Args:
            html: HTML内容

        Returns:
            结构化事件列表
        """
        from src.utils.logger import get_logger
        logger = get_logger(__name__)

        soup = BeautifulSoup(html, "html.parser")
        events = []

        # Investing.com 日历表格结构
        # 查找经济日历表格 (经济日历页面的ID通常是 economicCalendarData)
        calendar_table = soup.find("table", {"id": "economicCalendarData"})

        if not calendar_table:
            # 尝试其他可能的选择器
            calendar_table = soup.find("table", {"class": "genTbl"})

        if not calendar_table:
            logger.warning("calendar_table_not_found", html_length=len(html))
            return {
                "events": [],
                "count": 0,
                "parsed_at": datetime.utcnow().isoformat() + "Z",
                "error": "Calendar table not found"
            }

        # 尝试多种选择器模式
        rows = calendar_table.find_all("tr", {"class": "js-event-item"})
        if not rows:
            # 尝试备用选择器
            rows = calendar_table.find_all("tr", {"data-event-datetime": True})

        logger.info("calendar_rows_found", row_count=len(rows))

        for row in rows:
            try:
                event = self._parse_event_row(row)
                if event:
                    events.append(event)
            except Exception as e:
                # 跳过解析失败的行
                logger.warning("event_parse_failed", error=str(e))
                continue

        return {
            "events": events,
            "count": len(events),
            "parsed_at": datetime.utcnow().isoformat() + "Z",
        }

    def _parse_event_row(self, row) -> Optional[Dict[str, Any]]:
        """
        解析单个事件行

        Args:
            row: BeautifulSoup行对象

        Returns:
            事件字典
        """
        from src.utils.logger import get_logger
        logger = get_logger(__name__)

        try:
            # 时间
            time_cell = row.find("td", {"class": "time"})
            event_time = time_cell.text.strip() if time_cell else ""

            # 货币/国家
            currency_cell = row.find("td", {"class": "flagCur"})
            currency = ""
            if currency_cell:
                currency_span = currency_cell.find("span", {"class": "ceFlags"})
                if currency_span and currency_span.get("title"):
                    currency = currency_span["title"]

            # 重要性（1-3颗星）
            importance_cell = row.find("td", {"class": "sentiment"})
            importance = 0
            if importance_cell:
                bulls = importance_cell.find_all("i", {"class": "grayFullBullishIcon"})
                importance = len(bulls)

            # 事件名称
            event_cell = row.find("td", {"class": "event"})
            event_name = event_cell.text.strip() if event_cell else ""

            # 如果event_cell存在但name为空，记录详细信息
            if event_cell and not event_name:
                logger.warning(
                    "event_cell_empty",
                    html=str(event_cell)[:200],
                    all_classes=row.get("class", []),
                )
            elif not event_cell:
                # event_cell不存在 - 记录行的结构
                all_td_classes = [td.get("class", []) for td in row.find_all("td")[:5]]
                logger.warning(
                    "event_cell_not_found",
                    row_classes=row.get("class", []),
                    td_classes=all_td_classes,
                )

            # 实际值
            actual_cell = row.find("td", {"class": "act"})
            actual = actual_cell.text.strip() if actual_cell else ""

            # 预测值
            forecast_cell = row.find("td", {"class": "fore"})
            forecast = forecast_cell.text.strip() if forecast_cell else ""

            # 前值
            previous_cell = row.find("td", {"class": "prev"})
            previous = previous_cell.text.strip() if previous_cell else ""

            # 事件ID（用于后续查询详情）
            event_id = row.get("event_attr_id", "")

            # 只返回有效事件（至少有名称）
            if event_name:
                return {
                    "time": event_time,
                    "currency": currency,
                    "importance": importance,  # 1=低, 2=中, 3=高
                    "event": event_name,
                    "actual": actual,
                    "forecast": forecast,
                    "previous": previous,
                    "event_id": event_id,
                }

            return None

        except Exception as e:
            logger.warning("event_row_parse_exception", error=str(e))
            return None

    async def _get_cached_or_fetch(
        self, cache_key: str, fetch_func, ttl_seconds: int = 21600
    ) -> Any:
        """
        尝试从缓存获取，失败则调用fetch函数

        Args:
            cache_key: Redis缓存键
            fetch_func: 异步fetch函数
            ttl_seconds: 缓存TTL（默认6小时）

        Returns:
            缓存或新获取的数据
        """
        from src.utils.logger import get_logger
        logger = get_logger(__name__)

        # 尝试从Redis获取
        if self.redis_client:
            try:
                cached = await self.redis_client.get(cache_key)
                if cached:
                    logger.info(
                        "calendar_cache_hit",
                        cache_key=cache_key,
                    )
                    import json
                    return json.loads(cached)
            except Exception as e:
                logger.warning(
                    "calendar_cache_read_failed",
                    cache_key=cache_key,
                    error=str(e),
                )

        # 缓存未命中或失败，执行fetch
        data = await fetch_func()

        # 保存到Redis
        if self.redis_client:
            try:
                import json
                await self.redis_client.setex(
                    cache_key,
                    ttl_seconds,
                    json.dumps(data),
                )
                logger.info(
                    "calendar_cache_set",
                    cache_key=cache_key,
                    ttl_seconds=ttl_seconds,
                )
            except Exception as e:
                logger.warning(
                    "calendar_cache_write_failed",
                    cache_key=cache_key,
                    error=str(e),
                )

        return data

    async def get_economic_calendar(
        self, date: Optional[str] = None, importance: Optional[int] = None
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取经济日历（带缓存）

        Args:
            date: 日期 (YYYY-MM-DD格式，默认今天)
            importance: 最低重要性过滤 (1-3，3为最高)

        Returns:
            (日历数据, SourceMeta)
        """
        # 构建缓存键
        cache_date = date or datetime.utcnow().strftime("%Y-%m-%d")
        cache_key = f"calendar:{cache_date}:{importance or 0}"

        # 定义fetch函数
        async def fetch_calendar():
            # 构建URL参数
            params = {}
            if date:
                params["timeFrom"] = date.replace("-", "/")
                params["timeTo"] = date.replace("-", "/")

            if importance:
                params["importance"] = importance

            endpoint = "/economic-calendar/"

            raw_html, meta = await self.fetch(
                endpoint=endpoint,
                params=params,
                data_type="calendar",
                ttl_seconds=21600,  # 6小时TTL
            )

            # 客户端过滤（如需）
            if importance and raw_html.get("events"):
                raw_html["events"] = [
                    e for e in raw_html["events"] if e.get("importance", 0) >= importance
                ]
                raw_html["count"] = len(raw_html["events"])

            return raw_html

        # 使用缓存
        raw_html = await self._get_cached_or_fetch(
            cache_key=cache_key,
            fetch_func=fetch_calendar,
            ttl_seconds=21600,  # 6小时
        )

        # meta仍然新生成（反映查询时间）
        from src.core.source_meta import SourceMetaBuilder
        meta = SourceMetaBuilder.build(
            provider="investing_calendar",
            endpoint="/economic-calendar/",
            ttl_seconds=21600,
        )

        return raw_html, meta

    async def get_upcoming_events(
        self, days: int = 7, min_importance: int = 2
    ) -> tuple[List[Dict], SourceMeta]:
        """
        获取未来N天的重要事件

        Args:
            days: 未来天数
            min_importance: 最低重要性 (1-3)

        Returns:
            (事件列表, SourceMeta)
        """
        # 获取今天到未来days天的日历
        today = datetime.utcnow()
        end_date = today + timedelta(days=days)

        # Investing.com一次只能查询一天，所以需要循环查询
        all_events = []
        meta = None

        for i in range(days + 1):
            query_date = today + timedelta(days=i)
            date_str = query_date.strftime("%Y-%m-%d")

            try:
                data, meta = await self.get_economic_calendar(
                    date=date_str, importance=min_importance
                )
                if data.get("events"):
                    # 添加日期信息到每个事件
                    for event in data["events"]:
                        event["date"] = date_str
                    all_events.extend(data["events"])
            except Exception as e:
                # 单日查询失败不影响其他日期
                continue

        return all_events, meta or SourceMetaBuilder.build(
            provider="investing_calendar",
            endpoint="/economic-calendar/",
            ttl_seconds=600,
        )

    async def get_central_bank_events(
        self, days: int = 30
    ) -> tuple[List[Dict], SourceMeta]:
        """
        获取央行事件（利率决议、政策声明等）

        Args:
            days: 未来天数

        Returns:
            (央行事件列表, SourceMeta)
        """
        # 获取所有高重要性事件
        all_events, meta = await self.get_upcoming_events(
            days=days, min_importance=3
        )

        # 过滤央行相关关键词
        cb_keywords = [
            "interest rate",
            "rate decision",
            "monetary policy",
            "central bank",
            "fed ",
            "fomc",
            "ecb ",
            "boj ",
            "boe ",
        ]

        central_bank_events = []
        for event in all_events:
            event_name_lower = event.get("event", "").lower()
            if any(keyword in event_name_lower for keyword in cb_keywords):
                central_bank_events.append(event)

        return central_bank_events, meta
