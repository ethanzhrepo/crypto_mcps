"""
宏观经济数据API客户端

提供宏观经济指标：
- Alternative.me Fear & Greed Index (加密货币)
- 加密货币市场指数（通过CoinGecko）
- 传统金融指数（mock数据，可扩展到Yahoo Finance）
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.models import SourceMeta
from src.data_sources.base import BaseDataSource


class MacroDataClient(BaseDataSource):
    """宏观数据客户端"""

    FEAR_GREED_URL = "https://api.alternative.me"
    COINGECKO_URL = "https://api.coingecko.com/api/v3"

    def __init__(self):
        """初始化宏观数据客户端（无需API key）"""
        super().__init__(
            name="macro_data",
            base_url=self.FEAR_GREED_URL,  # Default base URL
            timeout=10.0,
            requires_api_key=False,
        )

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            "accept": "application/json",
        }

    async def fetch_raw(self, endpoint: str, params: Optional[Dict] = None, base_url_override: Optional[str] = None, headers: Optional[Dict[str, str]] = None) -> Any:
        """获取原始数据"""
        return await self._make_request("GET", endpoint, params, base_url_override, headers)

    async def get_fear_greed_index(
        self, limit: int = 1
    ) -> tuple[Dict, SourceMeta]:
        """
        获取加密货币恐惧贪婪指数

        Args:
            limit: 获取历史天数（1=仅今天，30=最近30天）

        Returns:
            (恐惧贪婪数据, 元信息)
        """
        endpoint = "/fng/"
        params = {"limit": limit}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="fear_greed",
            ttl_seconds=3600,  # 1小时缓存
            base_url_override=self.FEAR_GREED_URL,
        )

    async def get_crypto_indices(self) -> tuple[List[Dict], SourceMeta]:
        """
        获取加密货币市场指数

        Returns:
            (指数列表, 元信息)
        """
        # 使用CoinGecko的全球数据作为指数
        endpoint = "/global"
        params = {}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="crypto_indices",
            ttl_seconds=300,  # 5分钟缓存
            base_url_override=self.COINGECKO_URL,
        )

    def transform(self, raw_data: Any, data_type: str) -> Any:
        """转换原始数据为标准格式"""
        if data_type == "fear_greed":
            return self._transform_fear_greed(raw_data)
        elif data_type == "crypto_indices":
            return self._transform_crypto_indices(raw_data)
        return raw_data

    def _transform_fear_greed(self, data: Dict) -> Dict:
        """转换恐惧贪婪指数数据"""
        if not isinstance(data, dict) or "data" not in data:
            return {
                "value": 50,
                "classification": "neutral",
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }

        # 获取最新数据点
        latest = data["data"][0] if data["data"] else {}
        value = int(latest.get("value", 50))

        # 分类
        if value >= 75:
            classification = "extreme_greed"
        elif value >= 55:
            classification = "greed"
        elif value >= 45:
            classification = "neutral"
        elif value >= 25:
            classification = "fear"
        else:
            classification = "extreme_fear"

        return {
            "value": value,
            "classification": classification,
            "timestamp": datetime.fromtimestamp(
                int(latest.get("timestamp", datetime.utcnow().timestamp()))
            ).isoformat()
            + "Z",
        }

    def _transform_crypto_indices(self, data: Dict) -> List[Dict]:
        """转换加密货币指数数据"""
        if not isinstance(data, dict) or "data" not in data:
            return []

        global_data = data["data"]
        indices = []

        # 总市值
        total_market_cap = global_data.get("total_market_cap", {}).get("usd", 0)
        market_cap_change = global_data.get("market_cap_change_percentage_24h_usd", 0)

        indices.append(
            {
                "name": "Crypto Total Market Cap",
                "value": total_market_cap,
                "change_24h": total_market_cap * (market_cap_change / 100),
                "change_percent": market_cap_change,
            }
        )

        # BTC市值占比
        btc_dominance = global_data.get("market_cap_percentage", {}).get("btc", 0)
        indices.append(
            {
                "name": "Bitcoin Dominance",
                "value": btc_dominance,
                "change_24h": 0,  # CoinGecko不提供变化数据
                "change_percent": 0,
            }
        )

        # ETH市值占比
        eth_dominance = global_data.get("market_cap_percentage", {}).get("eth", 0)
        indices.append(
            {
                "name": "Ethereum Dominance",
                "value": eth_dominance,
                "change_24h": 0,
                "change_percent": 0,
            }
        )

        return indices
