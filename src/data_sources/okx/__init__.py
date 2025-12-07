"""
OKX Exchange API客户端

提供OKX交易所数据（用于多源对齐）：
- 行情数据（ticker, klines）
- 订单簿（order book）
- 最近成交（trades）
- 交易规格（instruments）
- 衍生品数据（资金费率、持仓量）
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.models import SourceMeta
from src.data_sources.base import BaseDataSource


class OKXClient(BaseDataSource):
    """OKX API客户端"""

    def __init__(self):
        """初始化OKX客户端（公开端点无需API key）"""
        super().__init__(
            name="okx",
            base_url="https://www.okx.com",
            timeout=10.0,
            requires_api_key=False,
        )

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def fetch_raw(
        self, endpoint: str, params: Optional[Dict] = None
    ) -> Any:
        """
        获取原始数据

        Args:
            endpoint: API端点
            params: 查询参数

        Returns:
            原始响应数据
        """
        return await self._make_request("GET", endpoint, params)

    def transform(self, raw_data: Any, data_type: str) -> Dict[str, Any]:
        """
        转换原始数据为标准格式

        Args:
            raw_data: 原始API响应
            data_type: 数据类型

        Returns:
            标准化数据
        """
        if data_type == "ticker":
            return self._transform_ticker(raw_data)
        elif data_type == "orderbook":
            return self._transform_orderbook(raw_data)
        elif data_type == "trades":
            return self._transform_trades(raw_data)
        elif data_type == "klines":
            return self._transform_klines(raw_data)
        elif data_type == "instruments":
            return self._transform_instruments(raw_data)
        elif data_type == "funding_rate":
            return self._transform_funding_rate(raw_data)
        else:
            return raw_data

    def _transform_ticker(self, data: Dict) -> Dict:
        """转换ticker数据"""
        if "data" not in data or not data["data"]:
            return {}

        ticker = data["data"][0]
        return {
            "symbol": ticker.get("instId"),
            "last_price": float(ticker.get("last", 0)),
            "bid_price": float(ticker.get("bidPx", 0)),
            "ask_price": float(ticker.get("askPx", 0)),
            "bid_size": float(ticker.get("bidSz", 0)),
            "ask_size": float(ticker.get("askSz", 0)),
            "volume_24h": float(ticker.get("vol24h", 0)),
            "volume_24h_ccy": float(ticker.get("volCcy24h", 0)),
            "open_24h": float(ticker.get("open24h", 0)),
            "high_24h": float(ticker.get("high24h", 0)),
            "low_24h": float(ticker.get("low24h", 0)),
            "timestamp": int(ticker.get("ts", 0)),
        }

    def _transform_orderbook(self, data: Dict) -> Dict:
        """转换订单簿数据"""
        if "data" not in data or not data["data"]:
            return {"bids": [], "asks": []}

        book = data["data"][0]
        bids = [[float(price), float(size)] for price, size, *_ in book.get("bids", [])]
        asks = [[float(price), float(size)] for price, size, *_ in book.get("asks", [])]

        return {
            "bids": bids,
            "asks": asks,
            "timestamp": int(book.get("ts", 0)),
        }

    def _transform_trades(self, data: Dict) -> Dict:
        """转换最近成交数据"""
        if "data" not in data:
            return {"trades": []}

        trades = []
        for trade in data["data"]:
            trades.append({
                "id": trade.get("tradeId"),
                "price": float(trade.get("px", 0)),
                "size": float(trade.get("sz", 0)),
                "side": trade.get("side"),  # buy or sell
                "timestamp": int(trade.get("ts", 0)),
            })

        return {"trades": trades, "count": len(trades)}

    def _transform_klines(self, data: Dict) -> Dict:
        """转换K线数据"""
        if "data" not in data:
            return {"candles": []}

        candles = []
        for candle in data["data"]:
            # OKX K线格式: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
            candles.append({
                "timestamp": int(candle[0]),
                "open": float(candle[1]),
                "high": float(candle[2]),
                "low": float(candle[3]),
                "close": float(candle[4]),
                "volume": float(candle[5]),
                "volume_ccy": float(candle[6]) if len(candle) > 6 else 0,
            })

        return {"candles": candles, "count": len(candles)}

    def _transform_instruments(self, data: Dict) -> Dict:
        """转换交易规格数据"""
        if "data" not in data or not data["data"]:
            return {}

        inst = data["data"][0]
        return {
            "symbol": inst.get("instId"),
            "base_currency": inst.get("baseCcy"),
            "quote_currency": inst.get("quoteCcy"),
            "tick_size": float(inst.get("tickSz", 0)),
            "lot_size": float(inst.get("lotSz", 0)),
            "min_size": float(inst.get("minSz", 0)),
            "contract_value": float(inst.get("ctVal", 1)),
            "state": inst.get("state"),
        }

    def _transform_funding_rate(self, data: Dict) -> Dict:
        """转换资金费率数据"""
        if "data" not in data or not data["data"]:
            return {}

        funding = data["data"][0]
        return {
            "symbol": funding.get("instId"),
            "funding_rate": float(funding.get("fundingRate", 0)),
            "next_funding_rate": float(funding.get("nextFundingRate", 0)),
            "funding_time": int(funding.get("fundingTime", 0)),
            "next_funding_time": int(funding.get("nextFundingTime", 0)),
        }

    async def get_ticker(
        self, inst_id: str
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取ticker数据

        Args:
            inst_id: 交易对ID（如 'BTC-USDT'）

        Returns:
            (ticker数据, SourceMeta)
        """
        endpoint = "/api/v5/market/ticker"
        params = {"instId": inst_id}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="ticker",
            ttl_seconds=60,
        )

    async def get_orderbook(
        self, inst_id: str, depth: int = 20
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取订单簿

        Args:
            inst_id: 交易对ID
            depth: 深度（可选值：1, 5, 10, 20, 50, 100, 200, 400）

        Returns:
            (订单簿数据, SourceMeta)
        """
        endpoint = "/api/v5/market/books"
        params = {
            "instId": inst_id,
            "sz": str(depth),
        }

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="orderbook",
            ttl_seconds=5,  # 5秒缓存
        )

    async def get_trades(
        self, inst_id: str, limit: int = 100
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取最近成交

        Args:
            inst_id: 交易对ID
            limit: 返回数量（最大500）

        Returns:
            (成交数据, SourceMeta)
        """
        endpoint = "/api/v5/market/trades"
        params = {
            "instId": inst_id,
            "limit": str(min(limit, 500)),
        }

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="trades",
            ttl_seconds=60,
        )

    async def get_klines(
        self,
        inst_id: str,
        bar: str = "1m",
        limit: int = 100,
        after: Optional[str] = None,
        before: Optional[str] = None,
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取K线数据

        Args:
            inst_id: 交易对ID
            bar: K线周期（1m/3m/5m/15m/30m/1H/2H/4H/6H/12H/1D/1W/1M/3M/6M/1Y）
            limit: 返回数量（最大300）
            after: 起始时间戳（毫秒）
            before: 结束时间戳（毫秒）

        Returns:
            (K线数据, SourceMeta)
        """
        endpoint = "/api/v5/market/candles"
        params = {
            "instId": inst_id,
            "bar": bar,
            "limit": str(min(limit, 300)),
        }

        if after:
            params["after"] = after
        if before:
            params["before"] = before

        # TTL根据时间周期调整
        ttl_map = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "1H": 3600,
            "1D": 21600,
        }
        ttl_seconds = ttl_map.get(bar, 300)

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="klines",
            ttl_seconds=ttl_seconds,
        )

    async def get_instruments(
        self,
        inst_type: str = "SPOT",
        inst_id: Optional[str] = None,
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取交易规格

        Args:
            inst_type: 产品类型（SPOT/MARGIN/SWAP/FUTURES/OPTION）
            inst_id: 特定交易对（可选）

        Returns:
            (交易规格, SourceMeta)
        """
        endpoint = "/api/v5/public/instruments"
        params = {"instType": inst_type}

        if inst_id:
            params["instId"] = inst_id

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="instruments",
            ttl_seconds=86400,  # 24小时
        )

    async def get_funding_rate(
        self, inst_id: str
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取永续合约资金费率

        Args:
            inst_id: 合约ID（如 'BTC-USDT-SWAP'）

        Returns:
            (资金费率数据, SourceMeta)
        """
        endpoint = "/api/v5/public/funding-rate"
        params = {"instId": inst_id}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="funding_rate",
            ttl_seconds=300,  # 5分钟
        )

    async def get_open_interest(
        self, inst_id: str
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取持仓量

        Args:
            inst_id: 合约ID

        Returns:
            (持仓量数据, SourceMeta)
        """
        endpoint = "/api/v5/public/open-interest"
        params = {"instId": inst_id}

        data, meta = await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="raw",
            ttl_seconds=120,  # 2分钟
        )

        # 转换OI数据
        if "data" in data and data["data"]:
            oi = data["data"][0]
            result = {
                "symbol": oi.get("instId"),
                "open_interest": float(oi.get("oi", 0)),
                "open_interest_ccy": float(oi.get("oiCcy", 0)),
                "timestamp": int(oi.get("ts", 0)),
            }
            return result, meta

        return {}, meta

    def normalize_symbol(self, symbol: str, market_type: str = "spot") -> str:
        """
        标准化交易对符号

        Args:
            symbol: 原始符号（如 'BTCUSDT'）
            market_type: 市场类型（spot/swap/futures）

        Returns:
            OKX格式符号（如 'BTC-USDT' 或 'BTC-USDT-SWAP'）
        """
        # 移除斜杠
        symbol = symbol.replace("/", "")

        # 分离base和quote
        if "USDT" in symbol:
            base = symbol.replace("USDT", "")
            quote = "USDT"
        elif "USD" in symbol:
            base = symbol.replace("USD", "")
            quote = "USD"
        elif "BTC" in symbol and symbol != "BTC":
            base = symbol.replace("BTC", "")
            quote = "BTC"
        elif "ETH" in symbol and symbol != "ETH":
            base = symbol.replace("ETH", "")
            quote = "ETH"
        else:
            # 默认假设USDT
            base = symbol
            quote = "USDT"

        # 构建OKX格式
        okx_symbol = f"{base}-{quote}"

        if market_type == "swap":
            okx_symbol += "-SWAP"
        elif market_type == "futures":
            # 期货需要添加交割日期，这里暂时返回永续
            okx_symbol += "-SWAP"

        return okx_symbol
