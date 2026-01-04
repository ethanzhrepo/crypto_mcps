"""
Yahoo Finance数据客户端 - 使用yfinance库

提供传统市场数据：
- 股票指数（标普500、纳斯达克等）
- 大宗商品（黄金、石油）
- 外汇（美元指数）
- 波动率指标（VIX）
"""
from typing import Any, Dict, List, Tuple

import yfinance as yf

from src.core.models import SourceMeta
from src.core.source_meta import SourceMetaBuilder
from src.utils.logger import get_logger

logger = get_logger(__name__)


class YahooFinanceClient:
    """Yahoo Finance客户端 - 基于yfinance库"""

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
        self.name = "yfinance"
        logger.info("yfinance_client_initialized", library_version=yf.__version__)

    def _transform_ticker_info(self, ticker_data: Dict) -> Dict:
        """转换yfinance Ticker.info为标准格式"""
        return {
            "symbol": ticker_data.get("symbol"),
            "name": ticker_data.get("longName") or ticker_data.get("shortName"),
            "price": ticker_data.get("currentPrice") or ticker_data.get("regularMarketPrice"),
            "change": ticker_data.get("regularMarketChange"),
            "change_percent": ticker_data.get("regularMarketChangePercent"),
            "previous_close": ticker_data.get("previousClose"),
            "open": ticker_data.get("regularMarketOpen"),
            "day_high": ticker_data.get("dayHigh"),
            "day_low": ticker_data.get("dayLow"),
            "volume": ticker_data.get("volume"),
            "market_cap": ticker_data.get("marketCap"),
            "currency": ticker_data.get("currency"),
            "exchange": ticker_data.get("fullExchangeName"),
        }

    async def get_quote(self, symbol: str) -> Tuple[Dict[str, Any], SourceMeta]:
        """
        获取单个股票/指数报价

        Args:
            symbol: 股票/指数符号（如 '^GSPC' 或 'AAPL'）

        Returns:
            (报价数据, SourceMeta)
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            if not info or not info.get("symbol"):
                raise ValueError(f"No data returned for symbol: {symbol}")

            data = self._transform_ticker_info(info)
            meta = SourceMetaBuilder.build(
                provider=self.name,
                endpoint=f"Ticker({symbol})",
                ttl_seconds=300,
            )

            return data, meta
        except Exception as e:
            logger.error("yfinance_get_quote_failed", symbol=symbol, error=str(e))
            raise

    async def get_multiple_quotes(
        self, symbols: List[str]
    ) -> Tuple[Dict[str, Any], SourceMeta]:
        """
        批量获取报价

        Args:
            symbols: 符号列表

        Returns:
            (多个报价, SourceMeta)
        """
        quotes = {}

        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                if info and info.get("symbol"):
                    quotes[symbol] = self._transform_ticker_info(info)
                else:
                    quotes[symbol] = None
            except Exception as e:
                logger.warning("yfinance_ticker_failed", symbol=symbol, error=str(e))
                quotes[symbol] = None

        meta = SourceMetaBuilder.build(
            provider=self.name,
            endpoint=f"Tickers({len(symbols)})",
            ttl_seconds=300,
        )

        return quotes, meta

    async def get_chart(
        self,
        symbol: str,
        interval: str = "1d",
        period: str = "1mo",
    ) -> Tuple[Dict[str, Any], SourceMeta]:
        """
        获取K线图表数据

        Args:
            symbol: 符号
            interval: K线间隔（1m/5m/15m/1h/1d/1wk/1mo）
            period: 时间范围（1d/5d/1mo/3mo/6mo/1y/2y/5y/max）

        Returns:
            (K线数据, SourceMeta)
        """
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval=interval)

            if hist.empty:
                raise ValueError(f"No chart data for {symbol}")

            candles = []
            for index, row in hist.iterrows():
                candles.append({
                    "timestamp": int(index.timestamp()),
                    "datetime": index.isoformat(),
                    "open": row["Open"],
                    "high": row["High"],
                    "low": row["Low"],
                    "close": row["Close"],
                    "volume": row["Volume"],
                })

            result = {
                "symbol": symbol,
                "candles": candles,
                "count": len(candles),
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

            meta = SourceMetaBuilder.build(
                provider=self.name,
                endpoint=f"history({symbol})",
                ttl_seconds=ttl_seconds,
            )

            return result, meta
        except Exception as e:
            logger.error("yfinance_get_chart_failed", symbol=symbol, error=str(e))
            raise

    async def get_market_indices(self) -> Tuple[Dict[str, Any], SourceMeta]:
        """
        获取主要市场指数

        Returns:
            (市场指数数据, SourceMeta)
        """
        symbols = [
            self.COMMON_SYMBOLS["sp500"],
            self.COMMON_SYMBOLS["nasdaq"],
            self.COMMON_SYMBOLS["dow"],
            self.COMMON_SYMBOLS["russell2000"],
            self.COMMON_SYMBOLS["vix"],
        ]

        quotes, meta = await self.get_multiple_quotes(symbols)

        return {
            "sp500": quotes.get(self.COMMON_SYMBOLS["sp500"]),
            "nasdaq": quotes.get(self.COMMON_SYMBOLS["nasdaq"]),
            "dow_jones": quotes.get(self.COMMON_SYMBOLS["dow"]),
            "russell2000": quotes.get(self.COMMON_SYMBOLS["russell2000"]),
            "vix": quotes.get(self.COMMON_SYMBOLS["vix"]),
        }, meta

    async def get_commodities(self) -> Tuple[Dict[str, Any], SourceMeta]:
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

    async def get_dollar_index(self) -> Tuple[Dict[str, Any], SourceMeta]:
        """
        获取美元指数

        Returns:
            (美元指数数据, SourceMeta)
        """
        return await self.get_quote(self.COMMON_SYMBOLS["dxy"])

    async def calculate_market_breadth(
        self,
    ) -> Tuple[Dict[str, Any], SourceMeta]:
        """
        计算市场广度指标

        Returns:
            (市场广度数据, SourceMeta)
        """
        # 获取主要指数
        indices_data, meta = await self.get_market_indices()

        sp500 = indices_data.get("sp500", {}) or {}
        vix = indices_data.get("vix", {}) or {}

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

    async def get_all_indicators(self) -> Tuple[Dict[str, Any], SourceMeta]:
        """
        获取所有指标（用于 MacroRawData 对齐 daily_analyzer）

        Returns:
            指标字典，键名与 daily_analyzer MacroRawData 字段对应:
            - 股指: sp500_price, nasdaq_price, dow_price, russell2000_price + 涨跌幅
            - VIX: vix
            - 美元: dxy_value, dxy_change_pct
            - 商品: gold_price, silver_price, crude_oil_price + 涨跌幅
            - 加密: btc_price, eth_price + 涨跌幅
        """
        result = {}

        # === 股指（价格 + 涨跌幅） ===
        try:
            sp500_data, meta = await self.get_quote(self.COMMON_SYMBOLS["sp500"])
            if sp500_data:
                result["sp500_price"] = sp500_data.get("price")
                result["sp500_change_pct"] = sp500_data.get("change_percent")
            else:
                result["sp500_price"] = None
                result["sp500_change_pct"] = None

            nasdaq_data, _ = await self.get_quote(self.COMMON_SYMBOLS["nasdaq"])
            if nasdaq_data:
                result["nasdaq_price"] = nasdaq_data.get("price")
                result["nasdaq_change_pct"] = nasdaq_data.get("change_percent")
            else:
                result["nasdaq_price"] = None
                result["nasdaq_change_pct"] = None

            dow_data, _ = await self.get_quote(self.COMMON_SYMBOLS["dow"])
            if dow_data:
                result["dow_price"] = dow_data.get("price")
                result["dow_change_pct"] = dow_data.get("change_percent")
            else:
                result["dow_price"] = None
                result["dow_change_pct"] = None

            russell2000_data, _ = await self.get_quote(self.COMMON_SYMBOLS["russell2000"])
            if russell2000_data:
                result["russell2000_price"] = russell2000_data.get("price")
                result["russell2000_change_pct"] = russell2000_data.get("change_percent")
            else:
                result["russell2000_price"] = None
                result["russell2000_change_pct"] = None

        except Exception as e:
            logger.error("yfinance_stock_indices_failed", error=str(e))

        # === 波动率 ===
        try:
            vix_data, _ = await self.get_quote(self.COMMON_SYMBOLS["vix"])
            result["vix"] = vix_data.get("price") if vix_data else None
        except Exception as e:
            logger.error("yfinance_vix_failed", error=str(e))

        # === 美元指数 ===
        try:
            dxy_data, _ = await self.get_quote(self.COMMON_SYMBOLS["dxy"])
            if dxy_data:
                result["dxy_value"] = dxy_data.get("price")
                result["dxy_change_pct"] = dxy_data.get("change_percent")
            else:
                result["dxy_value"] = None
                result["dxy_change_pct"] = None
        except Exception as e:
            logger.error("yfinance_dxy_failed", error=str(e))

        # === 大宗商品 ===
        try:
            gold_data, _ = await self.get_quote(self.COMMON_SYMBOLS["gold"])
            if gold_data:
                result["gold_price"] = gold_data.get("price")
                result["gold_change_pct"] = gold_data.get("change_percent")
            else:
                result["gold_price"] = None
                result["gold_change_pct"] = None

            silver_data, _ = await self.get_quote(self.COMMON_SYMBOLS["silver"])
            if silver_data:
                result["silver_price"] = silver_data.get("price")
                result["silver_change_pct"] = silver_data.get("change_percent")
            else:
                result["silver_price"] = None
                result["silver_change_pct"] = None

            crude_oil_data, _ = await self.get_quote(self.COMMON_SYMBOLS["crude_oil"])
            if crude_oil_data:
                result["crude_oil_price"] = crude_oil_data.get("price")
                result["crude_oil_change_pct"] = crude_oil_data.get("change_percent")
            else:
                result["crude_oil_price"] = None
                result["crude_oil_change_pct"] = None

        except Exception as e:
            logger.error("yfinance_commodities_failed", error=str(e))

        # === 加密货币（通过 YFinance） ===
        try:
            btc_data, _ = await self.get_quote(self.COMMON_SYMBOLS["btc_usd"])
            if btc_data:
                result["btc_price"] = btc_data.get("price")
                result["btc_change_pct"] = btc_data.get("change_percent")
            else:
                result["btc_price"] = None
                result["btc_change_pct"] = None

            eth_data, _ = await self.get_quote(self.COMMON_SYMBOLS["eth_usd"])
            if eth_data:
                result["eth_price"] = eth_data.get("price")
                result["eth_change_pct"] = eth_data.get("change_percent")
            else:
                result["eth_price"] = None
                result["eth_change_pct"] = None

        except Exception as e:
            logger.error("yfinance_crypto_failed", error=str(e))

        # 使用最后一个有效的 meta（或构建新的）
        meta = SourceMetaBuilder.build(
            provider=self.name,
            endpoint="get_all_indicators()",
            ttl_seconds=300,
        )

        return result, meta

