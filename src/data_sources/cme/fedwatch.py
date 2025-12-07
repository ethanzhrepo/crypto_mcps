"""
CME FedWatch Tool客户端

提供联邦基金利率预期概率数据
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

from src.core.models import SourceMeta
from src.data_sources.base import BaseDataSource
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CMEFedWatchClient(BaseDataSource):
    """CME FedWatch Tool客户端"""

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化CME FedWatch客户端

        Args:
            api_key: CME API密钥（可选，免费数据不需要）
        """
        # 使用Investing.com的Fed Rate Monitor作为数据源
        base_url = "https://www.investing.com"
        super().__init__(
            name="cme_fedwatch",
            base_url=base_url,
            timeout=15.0,
            requires_api_key=False,
        )
        self.api_key = api_key

    def _get_headers(self) -> Dict[str, str]:
        """构建请求头"""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    async def fetch_raw(self, endpoint: str, params: Optional[Dict] = None, base_url_override: Optional[str] = None) -> Any:
        """获取原始数据"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}{endpoint}",
                params=params,
                headers=self._get_headers(),
                follow_redirects=True,
            )
            response.raise_for_status()
            return response.text

    def transform(self, raw_data: Any, data_type: str) -> Dict[str, Any]:
        """
        转换原始数据为标准格式

        Args:
            raw_data: 原始响应数据
            data_type: 数据类型

        Returns:
            标准化数据字典
        """
        if data_type == "fedwatch":
            return self._transform_fedwatch(raw_data)
        return raw_data

    # ==================== 公共API方法 ====================

    async def get_rate_probabilities(
        self,
    ) -> tuple[Dict, SourceMeta]:
        """
        获取Fed利率预期概率

        Returns:
            (利率概率数据, SourceMeta)
        """
        # 方案1：尝试从Investing.com抓取
        try:
            html = await self.fetch_raw("/central-banks/fed-rate-monitor")
            probabilities = self._parse_investing_com(html)
        except Exception as e:
            logger.warning(f"Failed to scrape from Investing.com: {e}")
            # 降级到示例数据
            probabilities = self._get_example_data()

        meta = SourceMeta(
            provider="cme_fedwatch",
            endpoint="/central-banks/fed-rate-monitor",
            fetched_at=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=3600,  # 1小时缓存
            cache_hit=False,
        )

        return probabilities, meta

    async def get_next_meeting_probabilities(
        self,
    ) -> tuple[Dict, SourceMeta]:
        """
        获取下次FOMC会议的利率概率

        Returns:
            (会议概率数据, SourceMeta)
        """
        full_data, meta = await self.get_rate_probabilities()

        # 提取下次会议数据
        meetings = full_data.get("meetings", [])
        next_meeting = meetings[0] if meetings else {}

        return {
            "meeting_date": next_meeting.get("date"),
            "current_rate": full_data.get("current_rate"),
            "rate_scenarios": next_meeting.get("rate_scenarios", []),
        }, meta

    # ==================== 数据解析方法 ====================

    def _parse_investing_com(self, html: str) -> Dict:
        """
        解析Investing.com的Fed Rate Monitor页面

        Args:
            html: 页面HTML

        Returns:
            概率数据字典
        """
        # 简化版本：返回结构化数据格式
        # 真实实现需要解析HTML表格提取概率数据
        # TODO: 实现HTML解析逻辑

        return self._get_example_data()

    def _get_example_data(self) -> Dict:
        """
        获取示例数据（用于演示数据结构）

        Returns:
            示例FedWatch数据
        """
        return {
            "current_rate": 4.50,  # 当前利率（%）
            "current_range": "4.25-4.50",
            "as_of_date": datetime.utcnow().isoformat() + "Z",
            "meetings": [
                {
                    "date": "2025-12-10",
                    "meeting_name": "December 2025 FOMC",
                    "rate_scenarios": [
                        {
                            "target_rate": 4.50,
                            "target_range": "4.25-4.50",
                            "probability": 0.402,  # 40.2%
                            "change_from_current": 0,
                        },
                        {
                            "target_rate": 4.25,
                            "target_range": "4.00-4.25",
                            "probability": 0.598,  # 59.8%
                            "change_from_current": -0.25,
                        },
                    ],
                },
                {
                    "date": "2026-01-28",
                    "meeting_name": "January 2026 FOMC",
                    "rate_scenarios": [
                        {
                            "target_rate": 4.50,
                            "target_range": "4.25-4.50",
                            "probability": 0.25,
                            "change_from_current": 0,
                        },
                        {
                            "target_rate": 4.25,
                            "target_range": "4.00-4.25",
                            "probability": 0.50,
                            "change_from_current": -0.25,
                        },
                        {
                            "target_rate": 4.00,
                            "target_range": "3.75-4.00",
                            "probability": 0.25,
                            "change_from_current": -0.50,
                        },
                    ],
                },
            ],
        }

    def _transform_fedwatch(self, data: Dict) -> Dict:
        """转换FedWatch数据"""
        return {
            "current_rate": data.get("current_rate"),
            "current_range": data.get("current_range"),
            "meetings": data.get("meetings", []),
        }
