"""
Coinglass API客户端 - 清算数据

API文档: https://coinglass.com/api
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.models import BorrowRate, BorrowRatesData, LiquidationEvent, LiquidationsData, SourceMeta
from src.data_sources.base import BaseDataSource


class CoinglassClient(BaseDataSource):
    """Coinglass API客户端"""

    BASE_URL = "https://open-api-v4.coinglass.com"

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化Coinglass客户端

        Args:
            api_key: API密钥（可选，会尝试从配置中获取）
        """
        super().__init__(
            name="coinglass",
            base_url=self.BASE_URL,
            timeout=15.0,
            requires_api_key=True,
        )
        # 允许外部传入API密钥覆盖配置
        if api_key:
            self.api_key = api_key

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["coinglassSecret"] = self.api_key
        return headers

    async def fetch_raw(self, endpoint: str, params: Optional[Dict] = None, base_url_override: Optional[str] = None, headers: Optional[Dict[str, str]] = None) -> Any:
        """获取原始数据"""
        return await self._make_request("GET", endpoint, params, base_url_override, headers)

    def transform(self, raw_data: Any, data_type: str) -> Any:
        """转换原始数据"""
        if data_type == "liquidation_history":
            return self._transform_liquidation_history(raw_data)
        elif data_type == "liquidation_aggregated":
            return self._transform_liquidation_aggregated(raw_data)
        elif data_type == "borrow_rates":
            return raw_data  # 在get_borrow_rates方法中直接处理
        elif data_type == "open_interest_history":
            return raw_data  # 在get_open_interest_history方法中直接处理
        return raw_data

    async def get_liquidation_history(
        self,
        symbol: str,
        time_type: str = "h1",
        exchange: Optional[str] = None,
    ) -> tuple[Dict, SourceMeta]:
        """
        获取清算历史数据

        Args:
            symbol: 交易对符号，如 BTC, ETH
            time_type: 时间类型 m5(5分钟), m15, h1(1小时), h4, h12, h24
            exchange: 交易所（可选）

        Returns:
            (清算数据, SourceMeta)
        """
        endpoint = "/api/futures/liquidation/history"
        params = {
            "symbol": symbol.upper(),
            "time_type": time_type,
        }
        if exchange:
            params["ex"] = exchange

        data, meta = await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="liquidation_history",
            ttl_seconds=60,  # 清算数据1分钟TTL
        )
        return data, meta

    async def get_liquidation_aggregated(
        self,
        symbol: str,
        lookback_hours: int = 24,
    ) -> tuple[LiquidationsData, SourceMeta]:
        """
        获取聚合清算数据

        Args:
            symbol: 交易对符号
            lookback_hours: 回溯小时数

        Returns:
            (聚合清算数据, SourceMeta)
        """
        # 根据lookback_hours选择合适的time_type
        if lookback_hours <= 1:
            time_type = "h1"
        elif lookback_hours <= 4:
            time_type = "h4"
        elif lookback_hours <= 12:
            time_type = "h12"
        else:
            time_type = "h24"

        endpoint = "/api/futures/liquidation/aggregated-history"
        params = {
            "symbol": symbol.upper(),
            "time_type": time_type,
        }

        data, meta = await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="liquidation_aggregated",
            ttl_seconds=60,
        )

        # 构建LiquidationsData
        if isinstance(data, dict) and "aggregated" in data:
            agg = data["aggregated"]
            events = data.get("events", [])

            liquidations_data = LiquidationsData(
                symbol=symbol.upper(),
                exchange="aggregated",
                time_range_hours=lookback_hours,
                total_liquidations=agg.get("total_count", 0),
                total_value_usd=agg.get("total_value_usd", 0.0),
                long_liquidations=agg.get("long_count", 0),
                long_value_usd=agg.get("long_value_usd", 0.0),
                short_liquidations=agg.get("short_count", 0),
                short_value_usd=agg.get("short_value_usd", 0.0),
                events=[
                    LiquidationEvent(
                        symbol=e.get("symbol", symbol.upper()),
                        exchange=e.get("exchange", "unknown"),
                        side=e.get("side", "UNKNOWN"),
                        price=e.get("price", 0.0),
                        quantity=e.get("quantity", 0.0),
                        value_usd=e.get("value_usd", 0.0),
                        timestamp=e.get("timestamp", 0),
                    )
                    for e in events[:100]  # 限制事件数量
                ],
            )
            return liquidations_data, meta

        # 如果数据格式不符合预期，返回空数据
        return LiquidationsData(
            symbol=symbol.upper(),
            exchange="aggregated",
            time_range_hours=lookback_hours,
            total_liquidations=0,
            total_value_usd=0.0,
            long_liquidations=0,
            long_value_usd=0.0,
            short_liquidations=0,
            short_value_usd=0.0,
            events=[],
        ), meta

    def _transform_liquidation_history(self, raw_data: Any) -> Dict:
        """转换清算历史数据"""
        if not raw_data:
            return {"events": [], "aggregated": {}}

        # Coinglass API返回格式
        # {
        #   "code": "0",
        #   "msg": "success",
        #   "data": [...]
        # }
        data = raw_data.get("data", [])
        if not isinstance(data, list):
            data = []

        events = []
        total_long = 0
        total_short = 0
        total_long_value = 0.0
        total_short_value = 0.0

        for item in data:
            # Coinglass格式转换
            side = "LONG" if item.get("side") == 1 else "SHORT"
            value_usd = float(item.get("volUsd", 0))

            event = {
                "symbol": item.get("symbol", ""),
                "exchange": item.get("exchangeName", ""),
                "side": side,
                "price": float(item.get("price", 0)),
                "quantity": float(item.get("vol", 0)),
                "value_usd": value_usd,
                "timestamp": int(item.get("createTime", 0)),
            }
            events.append(event)

            if side == "LONG":
                total_long += 1
                total_long_value += value_usd
            else:
                total_short += 1
                total_short_value += value_usd

        return {
            "events": events,
            "aggregated": {
                "total_count": len(events),
                "total_value_usd": total_long_value + total_short_value,
                "long_count": total_long,
                "long_value_usd": total_long_value,
                "short_count": total_short,
                "short_value_usd": total_short_value,
            },
        }

    def _transform_liquidation_aggregated(self, raw_data: Any) -> Dict:
        """转换聚合清算数据（与历史数据使用相同转换）"""
        return self._transform_liquidation_history(raw_data)

    async def get_liquidation_chart(
        self,
        symbol: str,
        interval: str = "h1",
    ) -> tuple[List[Dict], SourceMeta]:
        """
        获取清算图表数据

        Args:
            symbol: 交易对符号
            interval: 时间间隔

        Returns:
            (图表数据列表, SourceMeta)
        """
        endpoint = "/api/futures/liquidation/chart"
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
        }

        data, meta = await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="liquidation_chart",
            ttl_seconds=60,
        )
        return data, meta

    async def get_borrow_rates(
        self,
        symbol: str,
    ) -> tuple[BorrowRatesData, SourceMeta]:
        """
        获取借贷利率数据

        Args:
            symbol: 代币符号 (如 BTC, ETH)

        Returns:
            (借贷利率数据, SourceMeta)
        """
        endpoint = "/api/borrow-interest-rate/history"
        params = {
            "symbol": symbol.upper(),
        }

        data, meta = await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="borrow_rates",
            ttl_seconds=300,  # 借贷利率5分钟TTL
        )

        # 构建BorrowRatesData
        if isinstance(data, dict) and "data" in data:
            raw_rates = data.get("data", [])
            rates = []

            for rate_item in raw_rates:
                # 根据Coinglass API响应格式解析
                rate = BorrowRate(
                    asset=symbol.upper(),
                    exchange=rate_item.get("exchange", "unknown"),
                    hourly_rate=float(rate_item.get("hourlyRate", 0.0)),
                    daily_rate=float(rate_item.get("dailyRate", 0.0)),
                    annual_rate=float(rate_item.get("annualRate", 0.0)),
                    available=float(rate_item.get("available", 0.0)),
                    timestamp=str(rate_item.get("timestamp", "")),
                )
                rates.append(rate)

            return BorrowRatesData(symbol=symbol.upper(), rates=rates), meta

        # 如果数据格式不符合预期，返回空数据
        return BorrowRatesData(symbol=symbol.upper(), rates=[]), meta

    async def get_open_interest_history(
        self,
        symbol: str,
        interval: str = "1h",
    ) -> tuple[List[Dict], SourceMeta]:
        """
        获取持仓量历史数据 (OHLC格式)

        Args:
            symbol: 代币符号 (如 BTC, ETH)
            interval: 时间间隔 (如 1h, 4h, 1d)

        Returns:
            (持仓量历史数据列表, SourceMeta)
        """
        # Correct v4 API endpoint (without ohlc- prefix)
        endpoint = "/api/futures/open-interest/aggregated-history"
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
        }

        data, meta = await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="open_interest_history",
            ttl_seconds=300,  # 持仓量数据5分钟TTL
        )

        # 返回数据列表
        if isinstance(data, dict) and "data" in data:
            return data.get("data", []), meta
        elif isinstance(data, list):
            return data, meta
        else:
            return [], meta

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            # 尝试获取BTC清算数据
            await self.get_liquidation_history("BTC", time_type="h1")
            return True
        except Exception:
            return False
