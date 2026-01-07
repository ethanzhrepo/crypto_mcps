"""
CryptoQuant API客户端

提供链上分析数据：
- 活跃地址 (Active Addresses)
- MVRV (Market Value to Realized Value)
- SOPR (Spent Output Profit Ratio)
- 交易所流量 (Exchange Flows)
- 矿工数据 (Miners)

API文档: https://cryptoquant.com/docs
"""
from datetime import datetime
from typing import Any, Dict, Optional

from src.core.models import SourceMeta
from src.data_sources.base import BaseDataSource


class CryptoQuantClient(BaseDataSource):
    """CryptoQuant API客户端"""

    BASE_URL = "https://api.cryptoquant.com"

    # 支持的资产
    SUPPORTED_ASSETS = {
        "BTC": "btc",
        "ETH": "eth",
        "USDT": "usdt",
        "USDC": "usdc",
    }

    def __init__(self) -> None:
        """初始化CryptoQuant客户端（需要API key）"""
        super().__init__(
            name="cryptoquant",
            base_url=self.BASE_URL,
            timeout=30.0,
            requires_api_key=True,
        )

    def _get_headers(self) -> Dict[str, str]:
        """构建请求头"""
        headers = {
            "accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def fetch_raw(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        base_url_override: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """获取原始数据"""
        return await self._make_request(
            "GET", endpoint, params, base_url_override, headers
        )

    def _normalize_symbol(self, symbol: str) -> str:
        """标准化代币符号"""
        upper = symbol.upper()
        return self.SUPPORTED_ASSETS.get(upper, upper.lower())

    # ==================== 活跃地址指标 ====================

    async def get_active_addresses(
        self,
        symbol: str = "BTC",
        window: str = "day",
        limit: int = 30,
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取活跃地址数量

        Args:
            symbol: 资产符号 (BTC, ETH)
            window: 时间窗口 (hour, day, block)
            limit: 返回数据点数量

        Returns:
            (活跃地址数据, 元信息)
        """
        asset = self._normalize_symbol(symbol)
        endpoint = f"/v1/network/{asset}/active-addresses"
        params = {"window": window, "limit": limit}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="active_addresses",
            ttl_seconds=3600,  # 1小时缓存
        )

    # ==================== 估值指标 ====================

    async def get_mvrv_ratio(
        self,
        symbol: str = "BTC",
        window: str = "day",
        limit: int = 30,
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取MVRV比率

        MVRV = Market Value / Realized Value
        - > 3.7: 可能顶部（超买）
        - < 1.0: 可能底部（超卖）
        - 1.0-2.0: 正常区间

        Args:
            symbol: 资产符号
            window: 时间窗口
            limit: 数据点数量

        Returns:
            (MVRV数据, 元信息)
        """
        asset = self._normalize_symbol(symbol)
        endpoint = f"/v1/market/{asset}/mvrv"
        params = {"window": window, "limit": limit}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="mvrv",
            ttl_seconds=3600,
        )

    async def get_sopr(
        self,
        symbol: str = "BTC",
        holder_type: str = "all",
        window: str = "day",
        limit: int = 30,
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取SOPR (Spent Output Profit Ratio)

        SOPR = 花费产出的实现价格 / 购入价格
        - > 1: 卖出者平均获利
        - < 1: 卖出者平均亏损
        - = 1: 盈亏平衡点

        Args:
            symbol: 资产符号
            holder_type: 持有者类型 (all, short_term, long_term)
            window: 时间窗口
            limit: 数据点数量

        Returns:
            (SOPR数据, 元信息)
        """
        asset = self._normalize_symbol(symbol)

        # 根据持有者类型选择端点
        if holder_type == "long_term":
            endpoint = f"/v1/market/{asset}/sopr-lth"
        elif holder_type == "short_term":
            endpoint = f"/v1/market/{asset}/sopr-sth"
        else:
            endpoint = f"/v1/market/{asset}/sopr"

        params = {"window": window, "limit": limit}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="sopr",
            ttl_seconds=3600,
        )

    # ==================== 交易所流量指标 ====================

    async def get_exchange_reserve(
        self,
        symbol: str = "BTC",
        exchange: Optional[str] = None,
        window: str = "day",
        limit: int = 30,
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取交易所储备量

        Args:
            symbol: 资产符号
            exchange: 特定交易所（可选）
            window: 时间窗口
            limit: 数据点数量

        Returns:
            (储备量数据, 元信息)
        """
        asset = self._normalize_symbol(symbol)

        if exchange:
            endpoint = f"/v1/exchange/{asset}/reserve/{exchange}"
        else:
            endpoint = f"/v1/exchange/{asset}/reserve"

        params = {"window": window, "limit": limit}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="exchange_reserve",
            ttl_seconds=1800,  # 30分钟缓存
        )

    async def get_exchange_netflow(
        self,
        symbol: str = "BTC",
        exchange: Optional[str] = None,
        window: str = "day",
        limit: int = 30,
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取交易所净流量

        净流量 = 流入 - 流出
        - 正值: 净流入（可能抛压）
        - 负值: 净流出（可能囤币）

        Args:
            symbol: 资产符号
            exchange: 特定交易所（可选）
            window: 时间窗口
            limit: 数据点数量

        Returns:
            (净流量数据, 元信息)
        """
        asset = self._normalize_symbol(symbol)

        if exchange:
            endpoint = f"/v1/exchange/{asset}/netflow/{exchange}"
        else:
            endpoint = f"/v1/exchange/{asset}/netflow"

        params = {"window": window, "limit": limit}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="exchange_netflow",
            ttl_seconds=1800,
        )

    async def get_exchange_inflow(
        self,
        symbol: str = "BTC",
        window: str = "day",
        limit: int = 30,
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取交易所流入量

        Args:
            symbol: 资产符号
            window: 时间窗口
            limit: 数据点数量

        Returns:
            (流入数据, 元信息)
        """
        asset = self._normalize_symbol(symbol)
        endpoint = f"/v1/exchange/{asset}/inflow"
        params = {"window": window, "limit": limit}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="exchange_inflow",
            ttl_seconds=1800,
        )

    async def get_exchange_outflow(
        self,
        symbol: str = "BTC",
        window: str = "day",
        limit: int = 30,
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取交易所流出量

        Args:
            symbol: 资产符号
            window: 时间窗口
            limit: 数据点数量

        Returns:
            (流出数据, 元信息)
        """
        asset = self._normalize_symbol(symbol)
        endpoint = f"/v1/exchange/{asset}/outflow"
        params = {"window": window, "limit": limit}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="exchange_outflow",
            ttl_seconds=1800,
        )

    # ==================== 矿工指标 ====================

    async def get_miner_reserve(
        self,
        symbol: str = "BTC",
        window: str = "day",
        limit: int = 30,
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取矿工储备量

        Args:
            symbol: 资产符号 (仅BTC)
            window: 时间窗口
            limit: 数据点数量

        Returns:
            (矿工储备数据, 元信息)
        """
        asset = self._normalize_symbol(symbol)
        endpoint = f"/v1/miner/{asset}/reserve"
        params = {"window": window, "limit": limit}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="miner_reserve",
            ttl_seconds=3600,
        )

    async def get_miner_outflow(
        self,
        symbol: str = "BTC",
        window: str = "day",
        limit: int = 30,
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取矿工流出量（可能的抛压指标）

        Args:
            symbol: 资产符号 (仅BTC)
            window: 时间窗口
            limit: 数据点数量

        Returns:
            (矿工流出数据, 元信息)
        """
        asset = self._normalize_symbol(symbol)
        endpoint = f"/v1/miner/{asset}/outflow"
        params = {"window": window, "limit": limit}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="miner_outflow",
            ttl_seconds=3600,
        )

    # ==================== 资金费率 ====================

    async def get_funding_rate(
        self,
        symbol: str = "BTC",
        exchange: Optional[str] = None,
        limit: int = 30,
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取永续合约资金费率

        Args:
            symbol: 资产符号
            exchange: 特定交易所（可选）
            limit: 数据点数量

        Returns:
            (资金费率数据, 元信息)
        """
        asset = self._normalize_symbol(symbol)

        if exchange:
            endpoint = f"/v1/derivatives/{asset}/funding-rate/{exchange}"
        else:
            endpoint = f"/v1/derivatives/{asset}/funding-rate"

        params = {"limit": limit}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="funding_rate",
            ttl_seconds=300,  # 5分钟缓存（更新频繁）
        )

    # ==================== 数据转换方法 ====================

    def transform(self, raw_data: Any, data_type: str) -> Any:
        """
        转换原始数据为标准格式

        Args:
            raw_data: CryptoQuant API原始响应
            data_type: 数据类型

        Returns:
            标准化数据
        """
        if data_type == "active_addresses":
            return self._transform_active_addresses(raw_data)
        elif data_type == "mvrv":
            return self._transform_mvrv(raw_data)
        elif data_type == "sopr":
            return self._transform_sopr(raw_data)
        elif data_type == "exchange_reserve":
            return self._transform_exchange_reserve(raw_data)
        elif data_type == "exchange_netflow":
            return self._transform_exchange_netflow(raw_data)
        elif data_type in ("exchange_inflow", "exchange_outflow"):
            return self._transform_exchange_flow(raw_data)
        elif data_type in ("miner_reserve", "miner_outflow"):
            return self._transform_miner_data(raw_data)
        elif data_type == "funding_rate":
            return self._transform_funding_rate(raw_data)
        else:
            return raw_data

    def _transform_active_addresses(self, data: Any) -> Dict[str, Any]:
        """转换活跃地址数据"""
        result = data.get("result", {})
        data_points = result.get("data", [])

        if not data_points:
            return {"active_addresses": 0, "history": []}

        latest = data_points[-1] if data_points else {}
        return {
            "active_addresses": latest.get("value", 0),
            "timestamp": latest.get("date", datetime.utcnow().isoformat()),
            "history": [
                {"date": d.get("date"), "value": d.get("value")}
                for d in data_points[-30:]
            ],
            "change_24h_pct": self._calculate_change(data_points, 1),
            "change_7d_pct": self._calculate_change(data_points, 7),
        }

    def _transform_mvrv(self, data: Any) -> Dict[str, Any]:
        """转换MVRV数据"""
        result = data.get("result", {})
        data_points = result.get("data", [])

        if not data_points:
            return {"mvrv_ratio": 1.0, "signal": "neutral"}

        latest = data_points[-1] if data_points else {}
        mvrv = latest.get("value", 1.0)

        # 判断信号
        if mvrv > 3.7:
            signal = "extreme_overvalued"
        elif mvrv > 2.5:
            signal = "overvalued"
        elif mvrv > 1.0:
            signal = "neutral"
        elif mvrv > 0.8:
            signal = "undervalued"
        else:
            signal = "extreme_undervalued"

        return {
            "mvrv_ratio": mvrv,
            "signal": signal,
            "timestamp": latest.get("date", datetime.utcnow().isoformat()),
            "history": [
                {"date": d.get("date"), "value": d.get("value")}
                for d in data_points[-30:]
            ],
        }

    def _transform_sopr(self, data: Any) -> Dict[str, Any]:
        """转换SOPR数据"""
        result = data.get("result", {})
        data_points = result.get("data", [])

        if not data_points:
            return {"sopr": 1.0, "signal": "neutral"}

        latest = data_points[-1] if data_points else {}
        sopr = latest.get("value", 1.0)

        # 判断信号
        if sopr > 1.05:
            signal = "profit_taking"
        elif sopr > 1.0:
            signal = "slight_profit"
        elif sopr > 0.95:
            signal = "slight_loss"
        else:
            signal = "capitulation"

        return {
            "sopr": sopr,
            "signal": signal,
            "timestamp": latest.get("date", datetime.utcnow().isoformat()),
            "history": [
                {"date": d.get("date"), "value": d.get("value")}
                for d in data_points[-30:]
            ],
        }

    def _transform_exchange_reserve(self, data: Any) -> Dict[str, Any]:
        """转换交易所储备数据"""
        result = data.get("result", {})
        data_points = result.get("data", [])

        if not data_points:
            return {"reserve": 0, "reserve_usd": 0}

        latest = data_points[-1] if data_points else {}
        return {
            "reserve": latest.get("value", 0),
            "reserve_usd": latest.get("value_usd", 0),
            "timestamp": latest.get("date", datetime.utcnow().isoformat()),
            "change_24h_pct": self._calculate_change(data_points, 1),
            "change_7d_pct": self._calculate_change(data_points, 7),
        }

    def _transform_exchange_netflow(self, data: Any) -> Dict[str, Any]:
        """转换交易所净流量数据"""
        result = data.get("result", {})
        data_points = result.get("data", [])

        if not data_points:
            return {"netflow": 0, "netflow_usd": 0, "signal": "neutral"}

        latest = data_points[-1] if data_points else {}
        netflow = latest.get("value", 0)

        # 判断信号
        if netflow > 0:
            signal = "bearish"  # 净流入 = 可能抛压
        elif netflow < 0:
            signal = "bullish"  # 净流出 = 可能囤币
        else:
            signal = "neutral"

        return {
            "netflow": netflow,
            "netflow_usd": latest.get("value_usd", 0),
            "signal": signal,
            "timestamp": latest.get("date", datetime.utcnow().isoformat()),
            "history": [
                {"date": d.get("date"), "value": d.get("value")}
                for d in data_points[-30:]
            ],
        }

    def _transform_exchange_flow(self, data: Any) -> Dict[str, Any]:
        """转换交易所流入/流出数据"""
        result = data.get("result", {})
        data_points = result.get("data", [])

        if not data_points:
            return {"flow": 0, "flow_usd": 0}

        latest = data_points[-1] if data_points else {}
        return {
            "flow": latest.get("value", 0),
            "flow_usd": latest.get("value_usd", 0),
            "timestamp": latest.get("date", datetime.utcnow().isoformat()),
            "change_24h_pct": self._calculate_change(data_points, 1),
        }

    def _transform_miner_data(self, data: Any) -> Dict[str, Any]:
        """转换矿工数据"""
        result = data.get("result", {})
        data_points = result.get("data", [])

        if not data_points:
            return {"value": 0}

        latest = data_points[-1] if data_points else {}
        return {
            "value": latest.get("value", 0),
            "value_usd": latest.get("value_usd", 0),
            "timestamp": latest.get("date", datetime.utcnow().isoformat()),
            "change_24h_pct": self._calculate_change(data_points, 1),
            "change_7d_pct": self._calculate_change(data_points, 7),
        }

    def _transform_funding_rate(self, data: Any) -> Dict[str, Any]:
        """转换资金费率数据"""
        result = data.get("result", {})
        data_points = result.get("data", [])

        if not data_points:
            return {"funding_rate": 0, "signal": "neutral"}

        latest = data_points[-1] if data_points else {}
        rate = latest.get("value", 0)

        # 判断信号
        if rate > 0.01:
            signal = "extreme_long"  # 多头杠杆过高
        elif rate > 0.005:
            signal = "long_bias"
        elif rate > -0.005:
            signal = "neutral"
        elif rate > -0.01:
            signal = "short_bias"
        else:
            signal = "extreme_short"  # 空头杠杆过高

        return {
            "funding_rate": rate,
            "funding_rate_annualized": rate * 3 * 365,  # 8小时一次 * 3 * 365
            "signal": signal,
            "timestamp": latest.get("date", datetime.utcnow().isoformat()),
            "history": [
                {"date": d.get("date"), "value": d.get("value")}
                for d in data_points[-30:]
            ],
        }

    def _calculate_change(self, data_points: list, days: int) -> float:
        """计算变化百分比"""
        if len(data_points) <= days:
            return 0.0

        current = data_points[-1].get("value", 0)
        previous = data_points[-(days + 1)].get("value", 0)

        if previous == 0:
            return 0.0

        return ((current - previous) / previous) * 100
