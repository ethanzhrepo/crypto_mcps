"""
Investing.com 财经日历爬虫

提供宏观财经事件日历：
- 央行决议（利率决定、货币政策）
- 经济数据发布（CPI、非农、GDP等）
- 财报季关键事件
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

from src.core.models import CalendarEvent, SourceMeta
from src.core.source_meta import SourceMetaBuilder
from src.data_sources.base import BaseDataSource


class InvestingCalendarClient(BaseDataSource):
    """Investing.com 财经日历客户端"""

    BASE_URL = "https://www.investing.com"

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        cache_enabled: bool = True,
        cache_file: Optional[str] = None,
    ):
        """初始化Investing.com日历客户端（无需API key）"""
        super().__init__(
            name="investing_calendar",
            base_url=self.BASE_URL,
            timeout=30.0,  # 增加timeout以适应浏览器
            requires_api_key=False,
        )
        # Redis缓存客户端（可选）
        self.redis_client = redis_client
        # JSON文件缓存配置
        self.cache_enabled = cache_enabled
        self.cache_file = cache_file or "cache/calendar_events.json"

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

    def _extract_xhr_defaults(self, html: str) -> Dict[str, str]:
        """从页面 HTML 中提取 XHR 所需的默认参数"""
        soup = BeautifulSoup(html, "html.parser")
        timezone = None
        time_filter = None

        tz_select = soup.find("select", {"id": "timeZone"})
        if tz_select:
            selected = tz_select.find("option", selected=True)
            if selected and selected.get("value"):
                timezone = selected["value"]

        time_filter_input = soup.find("input", {"name": "timeFilter", "checked": True})
        if time_filter_input and time_filter_input.get("value"):
            time_filter = time_filter_input["value"]

        return {
            "timeZone": timezone or "55",
            "timeFilter": time_filter or "timeRemain",
        }

    def _build_xhr_payload(
        self,
        date_from: str,
        date_to: str,
        min_importance: int,
        defaults: Dict[str, str],
    ) -> List[tuple]:
        """构建 XHR 请求的表单参数"""
        payload = [
            ("dateFrom", date_from),
            ("dateTo", date_to),
            ("timeZone", defaults.get("timeZone", "55")),
            ("timeFilter", defaults.get("timeFilter", "timeRemain")),
            ("currentTab", "custom"),
            ("submitFilters", "1"),
            ("limit_from", "0"),
        ]

        if min_importance:
            for importance in range(min_importance, 4):
                payload.append(("importance[]", str(importance)))

        return payload

    async def _fetch_html_with_xhr(
        self,
        date_str: str,
        min_importance: int,
    ) -> Optional[str]:
        """使用 XHR 接口拉取经济日历 HTML 片段（快速：2-3秒）"""
        from src.utils.logger import get_logger

        logger = get_logger(__name__)

        base_url = f"{self.base_url}/economic-calendar/"
        timeout = httpx.Timeout(20.0)
        headers = self._get_headers()

        try:
            async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as client:
                # Step 1: 获取基础页面以提取默认参数
                defaults = {"timeZone": "55", "timeFilter": "timeRemain"}
                try:
                    response = await client.get(base_url)
                    response.raise_for_status()
                    base_html = response.text
                    defaults = self._extract_xhr_defaults(base_html)
                except Exception as e:
                    logger.warning(f"Failed to fetch calendar defaults: {e}")

                # Step 2: 构建 POST payload
                payload = self._build_xhr_payload(
                    date_from=date_str,
                    date_to=date_str,
                    min_importance=min_importance,
                    defaults=defaults,
                )

                # Step 3: POST 到 XHR 端点
                post_headers = {
                    **headers,
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": base_url,
                    "Origin": self.base_url,
                }

                response = await client.post(
                    f"{base_url}Service/getCalendarFilteredData",
                    data=payload,
                    headers=post_headers,
                )
                response.raise_for_status()
                raw_text = response.text

                # Step 4: 解析 JSON 响应
                try:
                    payload_json = json.loads(raw_text)
                except json.JSONDecodeError:
                    logger.warning("XHR calendar response is not JSON")
                    return None

                html = payload_json.get("data") if isinstance(payload_json, dict) else None
                if not html:
                    logger.warning("XHR calendar response missing HTML data")
                    return None

                # Step 5: 包装 <tr> 片段为完整 table（便于 BeautifulSoup 解析）
                return f'<table id="economicCalendarData">{html}</table>'

        except Exception as e:
            logger.error(f"XHR calendar fetch failed for {date_str}: {e}")
            return None

    async def _fetch_html_with_playwright(self, url: str) -> Optional[str]:
        """使用 Playwright 获取 HTML（慢速但可靠：5-15秒）"""
        from playwright.async_api import async_playwright
        from src.utils.logger import get_logger

        logger = get_logger(__name__)

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],  # Docker 友好
                )

                page = await browser.new_page()
                await page.set_extra_http_headers(self._get_headers())

                # 导航到页面
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)

                # 等待经济日历表格加载
                await page.wait_for_selector(
                    "table#economicCalendarData, table.genTbl",
                    timeout=10000,
                )

                # 等待事件行加载
                await page.wait_for_selector(
                    "tr.js-event-item, tr[data-event-datetime]",
                    timeout=8000,
                    state="attached",
                )

                # 获取渲染后的 HTML
                html = await page.content()
                await browser.close()

                logger.info(f"Playwright fetched calendar HTML ({len(html)} bytes)")
                return html

        except Exception as e:
            logger.error(f"Playwright calendar fetch failed: {e}")
            return None

    def _load_cache_from_file(self) -> Dict[str, Any]:
        """加载日期缓存（JSON文件）"""
        if not self.cache_enabled:
            return {}

        cache_path = Path(self.cache_file)
        if not cache_path.exists():
            return {}

        from src.utils.logger import get_logger

        logger = get_logger(__name__)

        try:
            with cache_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception as e:
            logger.warning(f"Failed to load calendar cache: {e}")

        return {}

    def _save_cache_to_file(self, cache: Dict[str, Any]) -> None:
        """保存日期缓存（JSON文件）"""
        if not self.cache_enabled:
            return

        cache_path = Path(self.cache_file)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        from src.utils.logger import get_logger

        logger = get_logger(__name__)

        try:
            with cache_path.open("w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to save calendar cache: {e}")

    def _get_cached_events_from_file(
        self, cache: Dict[str, Any], date_str: str
    ) -> List[CalendarEvent]:
        """从文件缓存读取指定日期的事件列表"""
        cached = cache.get(date_str, {})
        events_data = cached.get("events", [])
        if not isinstance(events_data, list):
            return []
        return [CalendarEvent(**item) for item in events_data]

    def _update_cache_in_file(
        self, cache: Dict[str, Any], date_str: str, events: List[CalendarEvent]
    ) -> None:
        """更新指定日期的文件缓存"""
        cache[date_str] = {
            "fetched_at": datetime.utcnow().isoformat(),
            "events": [event.model_dump() for event in events],
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
        获取未来N天的重要事件 (XHR-first + dual caching)

        新策略:
        - XHR-first for speed (2-3s vs 5-15s)
        - Playwright fallback for reliability
        - Dual caching: Redis + JSON file
        - Per-date cache with smart TTL
        - Error isolation: single day failure doesn't break entire query

        Args:
            days: 未来天数
            min_importance: 最低重要性 (1-3)

        Returns:
            (事件列表, SourceMeta)
        """
        from src.utils.logger import get_logger

        logger = get_logger(__name__)

        all_events = []
        today = datetime.utcnow().date()

        # 加载 JSON 文件缓存
        file_cache = self._load_cache_from_file()
        cache_dirty = False

        for i in range(days + 1):
            query_date = today + timedelta(days=i)
            date_str = query_date.strftime("%Y-%m-%d")
            is_today = query_date == today

            # 确定缓存 key 和 TTL
            cache_key = f"calendar:{date_str}:{min_importance}"
            ttl = 600 if is_today else 21600  # 今天10分钟，未来6小时

            try:
                events: List[Dict] = []

                # Step 1: 尝试 Redis 缓存
                if self.redis_client and not is_today:
                    try:
                        cached = await self.redis_client.get(cache_key)
                        if cached:
                            events = json.loads(cached)
                            logger.info(f"Redis cache hit for {date_str}")
                    except Exception as e:
                        logger.warning(f"Redis read failed for {date_str}: {e}")

                # Step 2: 尝试文件缓存（如果 Redis 未命中且不是今天）
                if not events and not is_today:
                    cached_events = self._get_cached_events_from_file(file_cache, date_str)
                    if cached_events:
                        events = [e.model_dump() for e in cached_events]
                        logger.info(f"File cache hit for {date_str}")

                # Step 3: 如果缓存未命中或者是今天，则拉取新数据
                if not events or is_today:
                    # 3a. 尝试 XHR（快速：2-3秒）
                    html = await self._fetch_html_with_xhr(
                        date_str=date_str,
                        min_importance=min_importance,
                    )

                    # 3b. XHR 失败时回退到 Playwright（慢速：5-15秒）
                    if not html:
                        logger.warning(f"XHR failed for {date_str}, falling back to Playwright")
                        url_date = date_str.replace("-", "/")
                        url = f"{self.base_url}/economic-calendar/"
                        url += f"?timeFrom={url_date}&timeTo={url_date}"
                        if min_importance:
                            url += f"&importance={min_importance}"

                        html = await self._fetch_html_with_playwright(url)

                    # 3c. 解析 HTML
                    if html:
                        parsed = self._parse_calendar(html)
                        parsed_events = parsed.get("events", [])

                        # 转换为 CalendarEvent 对象
                        calendar_events = []
                        for evt_dict in parsed_events:
                            try:
                                evt_dict["date"] = date_str
                                cal_event = CalendarEvent(**evt_dict)
                                calendar_events.append(cal_event)
                            except Exception as e:
                                logger.warning(f"Failed to create CalendarEvent: {e}")
                                continue

                        events = [e.model_dump() for e in calendar_events]

                        # 更新缓存
                        if self.redis_client:
                            try:
                                await self.redis_client.setex(
                                    cache_key, ttl, json.dumps(events)
                                )
                            except Exception as e:
                                logger.warning(f"Redis write failed: {e}")

                        # 更新文件缓存
                        self._update_cache_in_file(file_cache, date_str, calendar_events)
                        cache_dirty = True
                    else:
                        # 3d. 所有拉取方法都失败，尝试使用旧的文件缓存
                        if not events:
                            cached_events = self._get_cached_events_from_file(file_cache, date_str)
                            if cached_events:
                                events = [e.model_dump() for e in cached_events]
                                logger.info(f"Using stale file cache for {date_str}")

                # 应用 importance 过滤
                filtered_events = [
                    e for e in events if e.get("importance", 0) >= min_importance
                ]

                # 确保每个事件都有 date 字段
                for event in filtered_events:
                    event["date"] = date_str

                all_events.extend(filtered_events)

                logger.info(
                    f"Fetched {len(filtered_events)} events for {date_str} "
                    f"(importance >= {min_importance})"
                )

            except Exception as e:
                # 错误隔离：记录错误但继续处理下一天
                logger.error(f"Failed to fetch calendar for {date_str}: {e}")
                continue

        # 保存文件缓存（如果有更新）
        if cache_dirty:
            self._save_cache_to_file(file_cache)

        # 构建 SourceMeta
        meta = SourceMetaBuilder.build(
            provider="investing_calendar",
            endpoint="/economic-calendar/",
            ttl_seconds=600,
        )

        return all_events, meta

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
