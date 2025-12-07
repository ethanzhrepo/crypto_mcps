"""
Yahoo Finance API客户端

提供传统市场数据：
- 股票指数（标普500、纳斯达克等）
- 大宗商品（黄金、石油）
- 外汇（美元指数）
- 波动率指标（VIX）
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from src.core.models import SourceMeta
from src.data_sources.base import BaseDataSource


class YahooFinanceClient(BaseDataSource):
    """Yahoo Finance API客户端"""

    # 常用市场符号
    COMMON_SYMBOLS = {
        # 美国股指
        "sp500": "^GSPC",  # 标普500
        "nasdaq": "^IXIC",  # 纳斯达克综合
        "dow": "^DJI",  # 道琼斯工业
        "russell2000": "^RUT",  # 罗素2000小盘股
        # 波动率
        "vix": "^VIX",  # CBOE波动率指数
        # 美元
        "dxy": "DX-Y.NYB",  # 美元指数期货
        # 大宗商品
        "gold": "GC=F",  # 黄金期货
        "silver": "SI=F",  # 白银期货
        "crude_oil": "CL=F",  # WTI原油期货
        "natural_gas": "NG=F",  # 天然气期货
        # 国债
        "treasury_10y": "^TNX",  # 10年期国债收益率
        "treasury_30y": "^TYX",  # 30年期国债收益率
        # 加密相关
        "btc_usd": "BTC-USD",  # 比特币
        "eth_usd": "ETH-USD",  # 以太坊
    }

    def __init__(self):
        """初始化Yahoo Finance客户端"""
        # Yahoo Finance使用query API，无需API key
        super().__init__(
            name="yfinance",
            base_url="https://query1.finance.yahoo.com",
            timeout=10.0,
            requires_api_key=False,
        )

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
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
        if data_type == "quote":
            return self._transform_quote(raw_data)
        elif data_type == "chart":
            return self._transform_chart(raw_data)
        else:
            return raw_data

    def _transform_quote(self, data: Dict) -> Dict:
        """转换报价数据"""
        if "quoteResponse" not in data or not data["quoteResponse"].get(
            "result"
        ):
            return {}

        quote = data["quoteResponse"]["result"][0]

        return {
            "symbol": quote.get("symbol"),
            "name": quote.get("longName") or quote.get("shortName"),
            "price": quote.get("regularMarketPrice"),
            "change": quote.get("regularMarketChange"),
            "change_percent": quote.get("regularMarketChangePercent"),
            "previous_close": quote.get("regularMarketPreviousClose"),
            "open": quote.get("regularMarketOpen"),
            "day_high": quote.get("regularMarketDayHigh"),
            "day_low": quote.get("regularMarketDayLow"),
            "volume": quote.get("regularMarketVolume"),
            "market_cap": quote.get("marketCap"),
            "timestamp": quote.get("regularMarketTime"),
            "currency": quote.get("currency"),
            "exchange": quote.get("fullExchangeName"),
        }

    def _transform_chart(self, data: Dict) -> Dict:
        """转换图表数据"""
        if "chart" not in data or not data["chart"].get("result"):
            return {"candles": []}

        result = data["chart"]["result"][0]
        meta = result.get("meta", {})
        timestamps = result.get("timestamp", [])
        indicators = result.get("indicators", {})
        quote_data = indicators.get("quote", [{}])[0]

        candles = []
        for i, ts in enumerate(timestamps):
            candle = {
                "timestamp": ts,
                "datetime": datetime.fromtimestamp(ts).isoformat() + "Z",
                "open": quote_data.get("open", [])[i],
                "high": quote_data.get("high", [])[i],
                "low": quote_data.get("low", [])[i],
                "close": quote_data.get("close", [])[i],
                "volume": quote_data.get("volume", [])[i],
            }
            candles.append(candle)

        return {
            "symbol": meta.get("symbol"),
            "currency": meta.get("currency"),
            "exchange": meta.get("exchangeName"),
            "candles": candles,
            "count": len(candles),
        }

    async def get_quote(
        self, symbol: str
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取实时报价

        Args:
            symbol: 股票/指数符号（如 '^GSPC' 或 'AAPL'）

        Returns:
            (报价数据, SourceMeta)
        """
        endpoint = "/v7/finance/quote"
        params = {"symbols": symbol}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="quote",
            ttl_seconds=300,  # 5分钟缓存
        )

    async def get_multiple_quotes(
        self, symbols: List[str]
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        批量获取报价

        Args:
            symbols: 符号列表

        Returns:
            (多个报价, SourceMeta)
        """
        endpoint = "/v7/finance/quote"
        symbols_str = ",".join(symbols)
        params = {"symbols": symbols_str}

        raw_data, meta = await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="raw",
            ttl_seconds=300,
        )

        # 转换每个报价
        quotes = {}
        if "quoteResponse" in raw_data and raw_data["quoteResponse"].get(
            "result"
        ):
            for quote in raw_data["quoteResponse"]["result"]:
                symbol = quote.get("symbol")
                quotes[symbol] = self._transform_quote(
                    {"quoteResponse": {"result": [quote]}}
                )

        return quotes, meta

    async def get_chart(
        self,
        symbol: str,
        interval: str = "1d",
        range_period: str = "1mo",
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取K线图表数据

        Args:
            symbol: 符号
            interval: K线间隔（1m/5m/15m/1h/1d/1wk/1mo）
            range_period: 时间范围（1d/5d/1mo/3mo/6mo/1y/2y/5y/max）

        Returns:
            (K线数据, SourceMeta)
        """
        endpoint = f"/v8/finance/chart/{symbol}"
        params = {
            "interval": interval,
            "range": range_period,
        }

        # 根据interval调整TTL
        ttl_map = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "1h": 3600,
            "1d": 21600,  # 6小时
            "1wk": 86400,  # 1天
            "1mo": 86400,
        }
        ttl_seconds = ttl_map.get(interval, 3600)

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="chart",
            ttl_seconds=ttl_seconds,
        )

    async def get_market_indices(self) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取主要市场指数

        Returns:
            (市场指数数据, SourceMeta)
        """
        symbols = [
            self.COMMON_SYMBOLS["sp500"],
            self.COMMON_SYMBOLS["nasdaq"],
            self.COMMON_SYMBOLS["dow"],
            self.COMMON_SYMBOLS["vix"],
        ]

        quotes, meta = await self.get_multiple_quotes(symbols)

        return {
            "sp500": quotes.get(self.COMMON_SYMBOLS["sp500"]),
            "nasdaq": quotes.get(self.COMMON_SYMBOLS["nasdaq"]),
            "dow_jones": quotes.get(self.COMMON_SYMBOLS["dow"]),
            "vix": quotes.get(self.COMMON_SYMBOLS["vix"]),
        }, meta

    async def get_commodities(self) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取大宗商品价格

        Returns:
            (大宗商品数据, SourceMeta)
        """
        symbols = [
            self.COMMON_SYMBOLS["gold"],
            self.COMMON_SYMBOLS["silver"],
            self.COMMON_SYMBOLS["crude_oil"],
        ]

        quotes, meta = await self.get_multiple_quotes(symbols)

        return {
            "gold": quotes.get(self.COMMON_SYMBOLS["gold"]),
            "silver": quotes.get(self.COMMON_SYMBOLS["silver"]),
            "crude_oil": quotes.get(self.COMMON_SYMBOLS["crude_oil"]),
        }, meta

    async def get_dollar_index(self) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取美元指数

        Returns:
            (美元指数数据, SourceMeta)
        """
        return await self.get_quote(self.COMMON_SYMBOLS["dxy"])

    async def calculate_market_breadth(
        self,
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        计算市场广度指标

        Returns:
            (市场广度数据, SourceMeta)
        """
        # 获取主要指数
        indices_data, meta = await self.get_market_indices()

        sp500 = indices_data.get("sp500", {})
        vix = indices_data.get("vix", {})

        # 简单的市场情绪判断
        sentiment = "neutral"
        if sp500.get("change_percent") is not None:
            change_pct = sp500["change_percent"]
            if change_pct > 1.0:
                sentiment = "bullish"
            elif change_pct < -1.0:
                sentiment = "bearish"

        # VIX恐慌等级
        fear_level = "normal"
        if vix.get("price") is not None:
            vix_value = vix["price"]
            if vix_value > 30:
                fear_level = "high"
            elif vix_value > 20:
                fear_level = "elevated"
            elif vix_value < 12:
                fear_level = "low"

        return {
            "market_sentiment": sentiment,
            "sp500_change_percent": sp500.get("change_percent"),
            "vix_level": vix.get("price"),
            "fear_level": fear_level,
            "indices": indices_data,
        }, meta
