"""
Binance数据源客户端

提供现货和合约市场数据：
- 实时行情 (ticker)
- K线数据 (klines)
- 成交记录 (trades)
- 订单簿 (orderbook)
- 交易规格 (exchange info)
"""
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from src.core.models import SourceMeta
from src.core.source_meta import SourceMetaBuilder
from src.data_sources.base import BaseDataSource


class BinanceClient(BaseDataSource):
    """Binance REST API客户端"""

    SPOT_BASE_URL = "https://api.binance.com"
    FUTURES_BASE_URL = "https://fapi.binance.com"

    def __init__(self, api_key: Optional[str] = None, use_testnet: bool = False):
        """
        初始化Binance客户端

        Args:
            api_key: API密钥（只读操作不需要）
            use_testnet: 是否使用测试网
        """
        base_url = self.SPOT_BASE_URL
        if use_testnet:
            base_url = "https://testnet.binance.vision"

        super().__init__(
            name="binance",
            base_url=base_url,
            timeout=10.0,
            requires_api_key=False,
        )
        self.api_key = api_key
        self.futures_base_url = self.FUTURES_BASE_URL

        if use_testnet:
            self.futures_base_url = "https://testnet.binancefuture.com"

    def _get_headers(self) -> Dict[str, str]:
        """构建请求头"""
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["X-MBX-APIKEY"] = self.api_key
        return headers

    async def fetch_raw(self, endpoint: str, params: Optional[Dict] = None, base_url_override: Optional[str] = None) -> Any:
        """获取原始数据"""
        return await self._make_request("GET", endpoint, params, base_url_override)

    # ==================== 公共方法 ====================

    async def get_ticker(
        self, symbol: str, market: str = "spot"
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取24h行情统计

        Args:
            symbol: 交易对，如 BTCUSDT
            market: 市场类型，spot或futures

        Returns:
            (数据字典, 元信息)
        """
        endpoint = "/api/v3/ticker/24hr"
        params = {"symbol": symbol.upper().replace("/", "")}
        base_url = self.base_url if market == "spot" else self.futures_base_url

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="ticker",
            ttl_seconds=5,  # 实时数据，短TTL
            base_url_override=base_url,
        )

    async def get_klines(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 100,
        market: str = "spot",
    ) -> tuple[List[Dict], SourceMeta]:
        """
        获取K线数据

        Args:
            symbol: 交易对
            interval: 周期 (1m, 5m, 15m, 1h, 4h, 1d, 1w, 1M)
            limit: 数量 (最大1000)
            market: 市场类型

        Returns:
            (K线数组, 元信息)
        """
        endpoint = "/api/v3/klines"
        params = {
            "symbol": symbol.upper().replace("/", ""),
            "interval": interval,
            "limit": min(limit, 1000),
        }
        base_url = self.base_url if market == "spot" else self.futures_base_url

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="klines",
            ttl_seconds=60,  # K线数据1分钟缓存
            base_url_override=base_url,
        )

    async def get_orderbook(
        self, symbol: str, limit: int = 20, market: str = "spot"
    ) -> tuple[Dict, SourceMeta]:
        """
        获取订单簿快照

        Args:
            symbol: 交易对
            limit: 深度档位 (5, 10, 20, 50, 100, 500, 1000, 5000)
            market: 市场类型

        Returns:
            (订单簿数据, 元信息)
        """
        endpoint = "/api/v3/depth"
        # Binance支持的limit值
        valid_limits = [5, 10, 20, 50, 100, 500, 1000, 5000]
        actual_limit = min(valid_limits, key=lambda x: abs(x - limit))

        params = {"symbol": symbol.upper().replace("/", ""), "limit": actual_limit}
        base_url = self.base_url if market == "spot" else self.futures_base_url

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="orderbook",
            ttl_seconds=1,  # 订单簿极短TTL
            base_url_override=base_url,
        )

    async def get_recent_trades(
        self, symbol: str, limit: int = 100, market: str = "spot"
    ) -> tuple[List[Dict], SourceMeta]:
        """
        获取最近成交记录

        Args:
            symbol: 交易对
            limit: 数量 (最大1000)
            market: 市场类型

        Returns:
            (成交数组, 元信息)
        """
        endpoint = "/api/v3/trades"
        params = {
            "symbol": symbol.upper().replace("/", ""),
            "limit": min(limit, 1000),
        }
        base_url = self.base_url if market == "spot" else self.futures_base_url

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="trades",
            ttl_seconds=10,
            base_url_override=base_url,
        )

    async def get_exchange_info(
        self, symbol: Optional[str] = None, market: str = "spot"
    ) -> tuple[Dict, SourceMeta]:
        """
        获取交易所规格信息

        Args:
            symbol: 交易对（可选，不指定则返回全部）
            market: 市场类型

        Returns:
            (规格数据, 元信息)
        """
        endpoint = "/api/v3/exchangeInfo"
        params = {}
        if symbol:
            params["symbol"] = symbol.upper().replace("/", "")

        base_url = self.base_url if market == "spot" else self.futures_base_url

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="exchange_info",
            ttl_seconds=3600,  # 规格信息变化少，长TTL
            base_url_override=base_url,
        )

    # ==================== 数据转换方法 ====================

    def transform(self, raw_data: Any, data_type: str) -> Any:
        """
        转换原始数据为标准格式

        Args:
            raw_data: Binance API原始响应
            data_type: 数据类型

        Returns:
            标准化数据
        """
        # 现货数据
        if data_type == "ticker":
            return self._transform_ticker(raw_data)
        elif data_type == "klines":
            return self._transform_klines(raw_data)
        elif data_type == "orderbook":
            return self._transform_orderbook(raw_data)
        elif data_type == "trades":
            return self._transform_trades(raw_data)
        elif data_type == "exchange_info":
            return self._transform_exchange_info(raw_data)
        # 衍生品数据
        elif data_type == "funding_rate":
            return self._transform_funding_rate(raw_data)
        elif data_type == "open_interest":
            return self._transform_open_interest(raw_data)
        elif data_type == "long_short_ratio":
            return self._transform_long_short_ratio(raw_data)
        elif data_type == "mark_price":
            return self._transform_funding_rate(raw_data)  # 相同格式
        else:
            return raw_data

    def _transform_ticker(self, data: Dict) -> Dict:
        """转换ticker数据"""
        return {
            "symbol": data["symbol"],
            "exchange": "binance",
            "last_price": float(data["lastPrice"]),
            "bid": float(data.get("bidPrice", 0)),
            "ask": float(data.get("askPrice", 0)),
            "spread_bps": self._calculate_spread_bps(
                float(data.get("bidPrice", 0)), float(data.get("askPrice", 0))
            ),
            "volume_24h": float(data["volume"]),
            "quote_volume_24h": float(data["quoteVolume"]),
            "price_change_24h": float(data["priceChange"]),
            "price_change_percent_24h": float(data["priceChangePercent"]),
            "high_24h": float(data["highPrice"]),
            "low_24h": float(data["lowPrice"]),
            "timestamp": datetime.fromtimestamp(data["closeTime"] / 1000).isoformat()
            + "Z",
        }

    def _transform_klines(self, data: List) -> List[Dict]:
        """转换K线数据"""
        return [
            {
                "open_time": kline[0],
                "open": float(kline[1]),
                "high": float(kline[2]),
                "low": float(kline[3]),
                "close": float(kline[4]),
                "volume": float(kline[5]),
                "close_time": kline[6],
                "quote_volume": float(kline[7]),
                "trades_count": int(kline[8]),
                "taker_buy_volume": float(kline[9]),
                "taker_buy_quote_volume": float(kline[10]),
            }
            for kline in data
        ]

    def _transform_orderbook(self, data: Dict) -> Dict:
        """转换订单簿数据"""
        bids = [[float(p), float(q)] for p, q in data["bids"]]
        asks = [[float(p), float(q)] for p, q in data["asks"]]

        # 计算累计量
        bids_with_total = []
        cumulative = 0.0
        for price, qty in bids:
            cumulative += qty
            bids_with_total.append({"price": price, "quantity": qty, "total": cumulative})

        asks_with_total = []
        cumulative = 0.0
        for price, qty in asks:
            cumulative += qty
            asks_with_total.append({"price": price, "quantity": qty, "total": cumulative})

        best_bid = bids[0][0] if bids else 0
        best_ask = asks[0][0] if asks else 0
        mid_price = (best_bid + best_ask) / 2 if best_bid and best_ask else 0

        # 计算前10档深度
        bid_depth_10 = sum([p * q for p, q in bids[:10]]) if len(bids) >= 10 else 0
        ask_depth_10 = sum([p * q for p, q in asks[:10]]) if len(asks) >= 10 else 0

        return {
            "symbol": data.get("symbol", ""),
            "exchange": "binance",
            "timestamp": data.get("lastUpdateId", int(time.time() * 1000)),
            "bids": bids_with_total,
            "asks": asks_with_total,
            "mid_price": mid_price,
            "spread_bps": self._calculate_spread_bps(best_bid, best_ask),
            "bid_depth_10": bid_depth_10,
            "ask_depth_10": ask_depth_10,
            "imbalance_ratio": bid_depth_10 / ask_depth_10 if ask_depth_10 > 0 else None,
        }

    def _transform_trades(self, data: List[Dict]) -> List[Dict]:
        """转换成交记录"""
        return [
            {
                "id": str(trade["id"]),
                "price": float(trade["price"]),
                "qty": float(trade["qty"]),
                "quote_qty": float(trade["quoteQty"]),
                "timestamp": trade["time"],
                "is_buyer_maker": trade["isBuyerMaker"],
                "side": "sell" if trade["isBuyerMaker"] else "buy",
            }
            for trade in data
        ]

    def _transform_exchange_info(self, data: Dict) -> Dict:
        """转换交易所规格信息"""
        if "symbol" in data:
            # 单个交易对
            return self._extract_symbol_info(data)
        elif "symbols" in data:
            # 多个交易对
            return {
                "symbols": [self._extract_symbol_info(s) for s in data["symbols"]]
            }
        return data

    def _extract_symbol_info(self, symbol_data: Dict) -> Dict:
        """提取单个交易对信息"""
        # 提取filters
        filters = {f["filterType"]: f for f in symbol_data.get("filters", [])}

        price_filter = filters.get("PRICE_FILTER", {})
        lot_size_filter = filters.get("LOT_SIZE", {})
        notional_filter = filters.get("MIN_NOTIONAL", {})

        return {
            "exchange": "binance",
            "symbol": symbol_data["symbol"],
            "base_asset": symbol_data["baseAsset"],
            "quote_asset": symbol_data["quoteAsset"],
            "status": symbol_data["status"],
            "tick_size": float(price_filter.get("tickSize", 0)),
            "lot_size": float(lot_size_filter.get("stepSize", 0)),
            "min_notional": float(notional_filter.get("minNotional", 0)),
            # Binance现货标准费率（可能因VIP等级不同）
            "maker_fee": 0.001,  # 0.1%
            "taker_fee": 0.001,  # 0.1%
        }

    # ==================== 辅助方法 ====================

    def _calculate_spread_bps(self, bid: float, ask: float) -> float:
        """
        计算买卖价差（基点）

        Args:
            bid: 买价
            ask: 卖价

        Returns:
            价差（基点，1bp = 0.01%）
        """
        if bid <= 0 or ask <= 0:
            return 0.0
        mid = (bid + ask) / 2
        return ((ask - bid) / mid) * 10000  # 转换为基点

    # ==================== 合约/衍生品方法 ====================

    async def get_funding_rate(
        self, symbol: str
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取永续合约资金费率

        Args:
            symbol: 交易对，如 BTCUSDT

        Returns:
            (资金费率数据, 元信息)
        """
        # 使用合约API
        endpoint = "/fapi/v1/premiumIndex"
        params = {"symbol": symbol.upper().replace("/", "")}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="funding_rate",
            ttl_seconds=60,
            base_url_override=self.futures_base_url,
        )

    async def get_open_interest(
        self, symbol: str
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取未平仓合约量

        Args:
            symbol: 交易对

        Returns:
            (未平仓量数据, 元信息)
        """
        endpoint = "/fapi/v1/openInterest"
        params = {"symbol": symbol.upper().replace("/", "")}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="open_interest",
            ttl_seconds=60,
            base_url_override=self.futures_base_url,
        )

    async def get_long_short_ratio(
        self, symbol: str, period: str = "1h"
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取多空比

        Args:
            symbol: 交易对
            period: 统计周期 (5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d)

        Returns:
            (多空比数据, 元信息)
        """
        # Binance提供多种多空比类型：账户数、持仓量、大户持仓
        endpoint = "/futures/data/globalLongShortAccountRatio"
        params = {"symbol": symbol.upper().replace("/", ""), "period": period, "limit": 1}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="long_short_ratio",
            ttl_seconds=300,
            base_url_override=self.futures_base_url,
        )

    async def get_mark_price(
        self, symbol: str
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取标记价格

        Args:
            symbol: 交易对

        Returns:
            (标记价格数据, 元信息)
        """
        endpoint = "/fapi/v1/premiumIndex"
        params = {"symbol": symbol.upper().replace("/", "")}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="mark_price",
            ttl_seconds=5,
            base_url_override=self.futures_base_url,
        )

    # ==================== 衍生品数据转换 ====================

    def _transform_funding_rate(self, data: Dict) -> Dict:
        """转换资金费率数据"""
        funding_rate = float(data["lastFundingRate"])
        # 资金费率8小时结算一次，年化 = rate * 3 * 365
        annual_rate = funding_rate * 3 * 365 * 100  # 转换为百分比

        return {
            "symbol": data["symbol"],
            "exchange": "binance",
            "funding_rate": funding_rate,
            "funding_rate_annual": annual_rate,
            "next_funding_time": datetime.fromtimestamp(
                data["nextFundingTime"] / 1000
            ).isoformat()
            + "Z",
            "mark_price": float(data["markPrice"]),
            "index_price": float(data.get("indexPrice", 0)),
            "timestamp": datetime.fromtimestamp(data["time"] / 1000).isoformat() + "Z",
        }

    def _transform_open_interest(self, data: Dict) -> Dict:
        """转换未平仓量数据"""
        return {
            "symbol": data["symbol"],
            "exchange": "binance",
            "open_interest": float(data["openInterest"]),
            # Note: 需要价格才能计算USD价值，这里先设为0
            "open_interest_usd": 0,
            "timestamp": datetime.fromtimestamp(data["time"] / 1000).isoformat() + "Z",
        }

    def _transform_long_short_ratio(self, data: List[Dict]) -> List[Dict]:
        """转换多空比数据"""
        if not data:
            return []

        result = []
        for item in data:
            long_ratio = float(item["longAccount"])
            short_ratio = float(item["shortAccount"])
            ls_ratio = long_ratio / short_ratio if short_ratio > 0 else 0

            result.append(
                {
                    "symbol": item["symbol"],
                    "exchange": "binance",
                    "ratio_type": "accounts",
                    "long_ratio": long_ratio,
                    "short_ratio": short_ratio,
                    "long_short_ratio": ls_ratio,
                    "timestamp": datetime.fromtimestamp(
                        item["timestamp"] / 1000
                    ).isoformat()
                    + "Z",
                }
            )

        return result
