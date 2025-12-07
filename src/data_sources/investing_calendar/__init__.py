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
from src.data_sources.base import BaseDataSource


class InvestingCalendarClient(BaseDataSource):
    """Investing.com 财经日历客户端"""

    BASE_URL = "https://www.investing.com"

    def __init__(self):
        """初始化Investing.com日历客户端（无需API key）"""
        super().__init__(
            name="investing_calendar",
            base_url=self.BASE_URL,
            timeout=15.0,
            requires_api_key=False,
        )

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
        self, endpoint: str, params: Optional[Dict] = None
    ) -> Any:
        """
        获取原始HTML数据

        Args:
            endpoint: 路径
            params: 查询参数

        Returns:
            HTML内容
        """
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                url,
                params=params,
                headers=self._get_headers(),
                follow_redirects=True,
            )
            response.raise_for_status()
            return response.text

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
        soup = BeautifulSoup(html, "html.parser")
        events = []

        # Investing.com 日历表格结构
        # 查找经济日历表格 (经济日历页面的ID通常是 economicCalendarData)
        calendar_table = soup.find("table", {"id": "economicCalendarData"})

        if not calendar_table:
            # 尝试其他可能的选择器
            calendar_table = soup.find("table", {"class": "genTbl"})

        if calendar_table:
            rows = calendar_table.find_all("tr", {"class": "js-event-item"})

            for row in rows:
                try:
                    event = self._parse_event_row(row)
                    if event:
                        events.append(event)
                except Exception as e:
                    # 跳过解析失败的行
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

        except Exception:
            return None

    async def get_economic_calendar(
        self, date: Optional[str] = None, importance: Optional[int] = None
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取经济日历

        Args:
            date: 日期 (YYYY-MM-DD格式，默认今天)
            importance: 最低重要性过滤 (1-3，3为最高)

        Returns:
            (日历数据, SourceMeta)
        """
        # 构建URL参数
        params = {}
        if date:
            # Investing.com使用特定的日期参数格式
            # 格式化为 timeFrom=YYYY/MM/DD&timeTo=YYYY/MM/DD
            params["timeFrom"] = date.replace("-", "/")
            params["timeTo"] = date.replace("-", "/")

        # 重要性过滤（URL参数）
        if importance:
            # importance=3 表示只显示高重要性
            params["importance"] = importance

        endpoint = "/economic-calendar/"

        raw_html, meta = await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="calendar",
            ttl_seconds=600,  # 10分钟缓存
        )

        # 如果需要importance过滤，在客户端再过滤一次
        if importance and raw_html.get("events"):
            raw_html["events"] = [
                e for e in raw_html["events"] if e.get("importance", 0) >= importance
            ]
            raw_html["count"] = len(raw_html["events"])

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

        return all_events, meta or SourceMeta(
            provider="investing_calendar",
            endpoint="/economic-calendar/",
            fetched_at=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=600,
            cache_hit=False,
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
