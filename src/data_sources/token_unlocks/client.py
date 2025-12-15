"""
Token Unlocks API客户端 - 代币解锁计划数据

API文档: https://token.unlocks.app/
注意: API需要联系获取访问权限
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.models import SourceMeta, TokenUnlockEvent, TokenUnlocksData
from src.data_sources.base import BaseDataSource


class TokenUnlocksClient(BaseDataSource):
    """Token Unlocks API客户端"""

    # 预留API URL，实际URL需要确认
    BASE_URL = "https://api.token.unlocks.app/v1"

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化Token Unlocks客户端

        Args:
            api_key: API密钥（必需）
        """
        super().__init__(
            name="token_unlocks",
            base_url=self.BASE_URL,
            timeout=15.0,
            requires_api_key=True,
        )
        if api_key:
            self.api_key = api_key

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def fetch_raw(self, endpoint: str, params: Optional[Dict] = None, base_url_override: Optional[str] = None, headers: Optional[Dict[str, str]] = None) -> Any:
        """获取原始数据"""
        return await self._make_request("GET", endpoint, params, base_url_override, headers)

    def transform(self, raw_data: Any, data_type: str) -> Any:
        """转换原始数据"""
        if data_type == "unlocks":
            return self._transform_unlocks(raw_data)
        return raw_data

    async def get_upcoming_unlocks(
        self,
        token_symbol: Optional[str] = None,
        days_ahead: int = 30,
        limit: int = 50,
    ) -> tuple[TokenUnlocksData, SourceMeta]:
        """
        获取即将到来的代币解锁

        Args:
            token_symbol: 代币符号过滤（可选）
            days_ahead: 查询未来多少天
            limit: 返回数量限制

        Returns:
            (解锁数据, SourceMeta)
        """
        endpoint = "/unlocks"
        params = {
            "days": days_ahead,
            "limit": limit,
        }
        if token_symbol:
            params["symbol"] = token_symbol.upper()

        data, meta = await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="unlocks",
            ttl_seconds=3600,  # 1小时缓存
        )

        # 转换为TokenUnlocksData
        events = data.get("events", [])
        total_value = sum(e.get("unlock_value_usd", 0) or 0 for e in events)

        # 找到最近的解锁日期
        next_unlock = None
        if events:
            sorted_events = sorted(events, key=lambda x: x.get("unlock_date", ""))
            next_unlock = sorted_events[0].get("unlock_date") if sorted_events else None

        unlocks_data = TokenUnlocksData(
            token_symbol=token_symbol.upper() if token_symbol else None,
            upcoming_unlocks=[
                TokenUnlockEvent(
                    project=e.get("project", ""),
                    token_symbol=e.get("token_symbol", ""),
                    unlock_date=e.get("unlock_date", ""),
                    unlock_amount=e.get("unlock_amount", 0),
                    unlock_value_usd=e.get("unlock_value_usd"),
                    percentage_of_supply=e.get("percentage_of_supply"),
                    cliff_type=e.get("cliff_type", "unknown"),
                    description=e.get("description"),
                    source="token_unlocks",
                )
                for e in events
            ],
            total_locked_value_usd=total_value,
            next_unlock_date=next_unlock,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

        return unlocks_data, meta

    async def get_token_vesting(
        self, token_symbol: str
    ) -> tuple[Dict, SourceMeta]:
        """
        获取代币vesting计划详情

        Args:
            token_symbol: 代币符号

        Returns:
            (vesting数据, SourceMeta)
        """
        endpoint = f"/token/{token_symbol.upper()}/vesting"

        return await self.fetch(
            endpoint=endpoint,
            params={},
            data_type="vesting",
            ttl_seconds=86400,  # 24小时缓存
        )

    def _transform_unlocks(self, raw_data: Any) -> Dict:
        """转换解锁数据"""
        if not raw_data:
            return {"events": []}

        # 假设API返回格式
        # {
        #   "status": "success",
        #   "data": [
        #     {
        #       "project": "Arbitrum",
        #       "token_symbol": "ARB",
        #       "unlock_date": "2025-03-16",
        #       "unlock_amount": 1000000,
        #       "unlock_value_usd": 2000000,
        #       "percentage_of_supply": 0.5,
        #       "cliff_type": "cliff"
        #     }
        #   ]
        # }

        data_list = raw_data.get("data", [])
        if isinstance(raw_data, list):
            data_list = raw_data

        events = []
        for item in data_list:
            events.append({
                "project": item.get("project", item.get("name", "")),
                "token_symbol": item.get("token_symbol", item.get("symbol", "")),
                "unlock_date": item.get("unlock_date", item.get("date", "")),
                "unlock_amount": item.get("unlock_amount", item.get("amount", 0)),
                "unlock_value_usd": item.get("unlock_value_usd", item.get("value_usd")),
                "percentage_of_supply": item.get("percentage_of_supply", item.get("percent")),
                "cliff_type": item.get("cliff_type", item.get("type", "unknown")),
                "description": item.get("description"),
            })

        return {"events": events}

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            # 尝试获取少量解锁数据
            data, _ = await self.get_upcoming_unlocks(days_ahead=7, limit=1)
            return True
        except Exception:
            return False
