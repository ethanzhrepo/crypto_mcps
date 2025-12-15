"""
market_microstructure 工具实现

提供实时市场微结构数据：
- ticker: 实时行情
- klines: K线数据
- trades: 成交记录
- orderbook: 订单簿
- volume_profile: 成交量价格分布
- taker_flow: 主动买卖流
- slippage: 滑点估算
- venue_specs: 场所规格
- sector_stats: 板块统计
"""
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import structlog

from src.core.models import (
    AggregatedOrderbook,
    Conflict,
    KlineData,
    MarketMicrostructureData,
    MarketMicrostructureInput,
    MarketMicrostructureOutput,
    OrderbookData,
    SectorStats,
    SlippageEstimate,
    SourceMeta,
    TakerFlow,
    TickerData,
    TradeData,
    VenueSpecs,
    VolumeProfile,
)
from src.data_sources.binance import BinanceClient
from src.data_sources.coingecko import CoinGeckoClient
from src.data_sources.okx import OKXClient
from src.tools.market.calculators import (
    OrderbookAggregator,
    SlippageEstimator,
    TakerFlowAnalyzer,
    VolumeProfileCalculator,
)

logger = structlog.get_logger()


class MarketMicrostructureTool:
    """market_microstructure工具"""

    def __init__(
        self,
        binance_client: Optional[BinanceClient] = None,
        okx_client: Optional[OKXClient] = None,
        coingecko_client: Optional[CoinGeckoClient] = None,
    ):
        """
        初始化market_microstructure工具

        Args:
            binance_client: Binance客户端（可选，默认创建新实例）
            okx_client: OKX客户端（可选，用于fallback）
            coingecko_client: CoinGecko客户端（可选，用于sector_stats）
        """
        self.binance = binance_client or BinanceClient()
        self.okx = okx_client  # Optional fallback source
        self.coingecko = coingecko_client  # Optional for sector stats

        # 计算器
        self.vp_calculator = VolumeProfileCalculator()
        self.slippage_estimator = SlippageEstimator()
        self.taker_flow_analyzer = TakerFlowAnalyzer()
        self.orderbook_aggregator = OrderbookAggregator()

        logger.info(
            "market_microstructure_tool_initialized",
            has_binance=True,
            has_okx_fallback=okx_client is not None,
            has_coingecko=coingecko_client is not None,
        )

    async def execute(
        self, params
    ) -> MarketMicrostructureOutput:
        """
        执行market_microstructure查询

        Args:
            params: 输入参数（可以是字典或MarketMicrostructureInput）

        Returns:
            MarketMicrostructureOutput
        """
        # 如果传入字典，转换为Pydantic模型
        if isinstance(params, dict):
            params = MarketMicrostructureInput(**params)

        start_time = time.time()
        logger.info(
            "market_microstructure_execute_start",
            symbol=params.symbol,
            venues=params.venues,
            fields=params.include_fields,
        )

        # 标准化交易对符号
        symbol = self._normalize_symbol(params.symbol)

        # 使用第一个venue作为主数据源
        primary_venue = params.venues[0] if params.venues else "binance"

        # 收集数据
        data = MarketMicrostructureData()
        source_metas = []
        conflicts = []
        warnings = []

        # 订单簿深度用于微观结构/滑点分析时，过小（例如 10/20）不具备分析价值。
        # 为保证分析质量，强制提升到至少 100 档。
        orderbook_depth = params.orderbook_depth
        needs_orderbook = (
            "all" in params.include_fields
            or "orderbook" in params.include_fields
            or "aggregated_orderbook" in params.include_fields
            or "slippage" in params.include_fields
        )
        if needs_orderbook and orderbook_depth < 100:
            warnings.append(f"orderbook_depth too small ({orderbook_depth}); increased to 100 for analysis quality")
            orderbook_depth = 100

        # 根据include_fields获取数据
        if "all" in params.include_fields or "ticker" in params.include_fields:
            ticker, meta = await self._fetch_ticker(symbol, primary_venue)
            data.ticker = ticker
            source_metas.append(meta)

        if "all" in params.include_fields or "klines" in params.include_fields:
            klines, meta = await self._fetch_klines(
                symbol, params.kline_interval, params.kline_limit, primary_venue
            )
            data.klines = klines
            source_metas.append(meta)

        if "all" in params.include_fields or "trades" in params.include_fields:
            trades, meta = await self._fetch_trades(
                symbol, params.trades_limit, primary_venue
            )
            data.trades = trades
            source_metas.append(meta)

        if "all" in params.include_fields or "orderbook" in params.include_fields:
            orderbook, meta = await self._fetch_orderbook(
                symbol, orderbook_depth, primary_venue
            )
            data.orderbook = orderbook
            source_metas.append(meta)

        if "all" in params.include_fields or "aggregated_orderbook" in params.include_fields:
            try:
                agg_orderbook, agg_meta = await self._fetch_aggregated_orderbook(
                    symbol, orderbook_depth, params.venues
                )
                data.aggregated_orderbook = agg_orderbook
                source_metas.extend(agg_meta)
            except Exception as e:
                logger.warning(f"Failed to fetch aggregated orderbook: {e}")
                warnings.append(f"aggregated_orderbook fetch failed: {str(e)}")

        # 计算型字段
        if "all" in params.include_fields or "volume_profile" in params.include_fields:
            if data.trades:
                volume_profile = self._calculate_volume_profile(symbol, data.trades, primary_venue)
                data.volume_profile = volume_profile
            else:
                warnings.append("volume_profile requires trades data")

        if "all" in params.include_fields or "taker_flow" in params.include_fields:
            if data.trades:
                taker_flow = self._calculate_taker_flow(symbol, data.trades, primary_venue)
                data.taker_flow = taker_flow
            else:
                warnings.append("taker_flow requires trades data")

        if "all" in params.include_fields or "slippage" in params.include_fields:
            if data.orderbook and data.ticker:
                slippage = self._estimate_slippage(
                    symbol,
                    data.orderbook,
                    data.ticker.last_price,
                    params.slippage_size_usd,
                    primary_venue,
                )
                data.slippage = slippage
            else:
                warnings.append("slippage requires orderbook and ticker data")

        if "all" in params.include_fields or "venue_specs" in params.include_fields:
            specs, meta = await self._fetch_venue_specs(symbol, primary_venue)
            data.venue_specs = specs
            source_metas.append(meta)

        # sector_stats（板块统计）
        if "all" in params.include_fields or "sector_stats" in params.include_fields:
            if self.coingecko:
                try:
                    sector_stats, meta = await self._fetch_sector_stats(symbol)
                    data.sector_stats = sector_stats
                    source_metas.append(meta)
                except Exception as e:
                    logger.warning(f"Failed to fetch sector_stats: {e}")
                    warnings.append(f"sector_stats fetch failed: {str(e)}")
            else:
                warnings.append("sector_stats requires CoinGecko client (not configured)")

        elapsed = time.time() - start_time
        logger.info(
            "market_microstructure_execute_complete",
            symbol=symbol,
            elapsed_ms=round(elapsed * 1000, 2),
        )

        return MarketMicrostructureOutput(
            symbol=symbol,
            exchange=primary_venue,
            data=data,
            source_meta=source_metas,
            conflicts=conflicts,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )

    # ==================== 数据获取方法 ====================

    async def _fetch_ticker(
        self, symbol: str, exchange: Optional[str]
    ) -> Tuple[TickerData, SourceMeta]:
        """获取ticker数据（支持Binance和OKX，自动fallback）"""
        exchange = exchange or "binance"

        if exchange == "binance":
            try:
                data, meta = await self.binance.get_ticker(symbol)
                return TickerData(**data), meta
            except Exception as e:
                if self.okx:
                    logger.warning(
                        f"Binance ticker failed, falling back to OKX: {e}",
                        symbol=symbol,
                    )
                    # Convert symbol format for OKX
                    okx_symbol = self.okx.normalize_symbol(symbol, "spot")
                    data, meta = await self.okx.get_ticker(okx_symbol)
                    return TickerData(**data), meta
                raise
        elif exchange == "okx":
            if not self.okx:
                raise ValueError("OKX client not configured")
            okx_symbol = self.okx.normalize_symbol(symbol, "spot")
            data, meta = await self.okx.get_ticker(okx_symbol)
            return TickerData(**data), meta
        else:
            raise ValueError(f"Unsupported exchange: {exchange}")

    async def _fetch_klines(
        self, symbol: str, interval: str, limit: int, exchange: Optional[str]
    ) -> Tuple[List[KlineData], SourceMeta]:
        """获取K线数据（支持Binance和OKX，自动fallback）"""
        exchange = exchange or "binance"

        if exchange == "binance":
            try:
                data, meta = await self.binance.get_klines(symbol, interval, limit)
                return [KlineData(**k) for k in data], meta
            except Exception as e:
                if self.okx:
                    logger.warning(
                        f"Binance klines failed, falling back to OKX: {e}",
                        symbol=symbol,
                    )
                    okx_symbol = self.okx.normalize_symbol(symbol, "spot")
                    data, meta = await self.okx.get_klines(okx_symbol, interval, limit)
                    return [KlineData(**k) for k in data], meta
                raise
        elif exchange == "okx":
            if not self.okx:
                raise ValueError("OKX client not configured")
            okx_symbol = self.okx.normalize_symbol(symbol, "spot")
            data, meta = await self.okx.get_klines(okx_symbol, interval, limit)
            return [KlineData(**k) for k in data], meta
        else:
            raise ValueError(f"Unsupported exchange: {exchange}")

    async def _fetch_trades(
        self, symbol: str, limit: int, exchange: Optional[str]
    ) -> Tuple[List[TradeData], SourceMeta]:
        """获取成交记录（支持Binance和OKX，自动fallback）"""
        exchange = exchange or "binance"

        if exchange == "binance":
            try:
                data, meta = await self.binance.get_recent_trades(symbol, limit)
                return [TradeData(**t) for t in data], meta
            except Exception as e:
                if self.okx:
                    logger.warning(
                        f"Binance trades failed, falling back to OKX: {e}",
                        symbol=symbol,
                    )
                    okx_symbol = self.okx.normalize_symbol(symbol, "spot")
                    data, meta = await self.okx.get_recent_trades(okx_symbol, limit)
                    return [TradeData(**t) for t in data], meta
                raise
        elif exchange == "okx":
            if not self.okx:
                raise ValueError("OKX client not configured")
            okx_symbol = self.okx.normalize_symbol(symbol, "spot")
            data, meta = await self.okx.get_recent_trades(okx_symbol, limit)
            return [TradeData(**t) for t in data], meta
        else:
            raise ValueError(f"Unsupported exchange: {exchange}")

    async def _fetch_orderbook(
        self, symbol: str, depth: int, exchange: Optional[str]
    ) -> Tuple[OrderbookData, SourceMeta]:
        """获取订单簿（支持Binance和OKX，自动fallback）"""
        exchange = exchange or "binance"

        if exchange == "binance":
            try:
                data, meta = await self.binance.get_orderbook(symbol, depth)
                data["symbol"] = symbol
                return OrderbookData(**data), meta
            except Exception as e:
                if self.okx:
                    logger.warning(
                        f"Binance orderbook failed, falling back to OKX: {e}",
                        symbol=symbol,
                    )
                    okx_symbol = self.okx.normalize_symbol(symbol, "spot")
                    data, meta = await self.okx.get_orderbook(okx_symbol, depth)
                    data["symbol"] = symbol
                    return OrderbookData(**data), meta
                raise
        elif exchange == "okx":
            if not self.okx:
                raise ValueError("OKX client not configured")
            okx_symbol = self.okx.normalize_symbol(symbol, "spot")
            data, meta = await self.okx.get_orderbook(okx_symbol, depth)
            data["symbol"] = symbol
            return OrderbookData(**data), meta
        else:
            raise ValueError(f"Unsupported exchange: {exchange}")

    async def _fetch_aggregated_orderbook(
        self, symbol: str, depth: int, venues: List[str]
    ) -> Tuple[AggregatedOrderbook, List[SourceMeta]]:
        """获取多个交易所的订单簿并聚合"""
        import asyncio
        from collections import defaultdict

        if not venues or len(venues) == 0:
            venues = ["binance"]  # 默认使用binance

        # 并行获取多个交易所的订单簿
        tasks = []
        valid_venues = []
        for venue in venues:
            if venue in ["binance", "okx"]:
                tasks.append(self._fetch_orderbook(symbol, depth, venue))
                valid_venues.append(venue)

        if not tasks:
            raise ValueError("No valid venues specified for aggregated orderbook")

        # 并行获取
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 收集成功的订单簿和元数据
        orderbooks = []
        metas = []
        successful_venues = []
        for venue, result in zip(valid_venues, results):
            if isinstance(result, Exception):
                logger.warning(f"Failed to fetch orderbook from {venue}: {result}")
                continue
            orderbook, meta = result
            orderbooks.append(orderbook)
            metas.append(meta)
            successful_venues.append(venue)

        if not orderbooks:
            raise ValueError("Failed to fetch orderbooks from all venues")

        # 聚合订单簿
        # 1. 合并所有买单和卖单
        all_bids = []
        all_asks = []
        for ob in orderbooks:
            all_bids.extend(ob.bids)
            all_asks.extend(ob.asks)

        # 2. 按价格聚合相同价格的订单
        bid_dict = defaultdict(float)
        ask_dict = defaultdict(float)

        for bid in all_bids:
            bid_dict[bid.price] += bid.quantity

        for ask in all_asks:
            ask_dict[ask.price] += ask.quantity

        # 3. 转换为列表并排序
        from src.core.models import OrderbookLevel
        aggregated_bids = [
            OrderbookLevel(price=price, quantity=qty)
            for price, qty in bid_dict.items()
        ]
        aggregated_asks = [
            OrderbookLevel(price=price, quantity=qty)
            for price, qty in ask_dict.items()
        ]

        # 买单按价格降序排序（最高买价在前）
        aggregated_bids.sort(key=lambda x: x.price, reverse=True)
        # 卖单按价格升序排序（最低卖价在前）
        aggregated_asks.sort(key=lambda x: x.price)

        # 限制深度
        aggregated_bids = aggregated_bids[:depth]
        aggregated_asks = aggregated_asks[:depth]

        # 4. 计算统计数据
        best_bid = aggregated_bids[0].price if aggregated_bids else 0.0
        best_ask = aggregated_asks[0].price if aggregated_asks else 0.0
        global_mid = (best_bid + best_ask) / 2 if best_bid and best_ask else 0.0

        # 计算总深度（USD）
        total_bid_depth_usd = sum(b.price * b.quantity for b in aggregated_bids)
        total_ask_depth_usd = sum(a.price * a.quantity for a in aggregated_asks)

        # 5. 构建聚合订单簿
        from datetime import datetime
        agg_orderbook = AggregatedOrderbook(
            symbol=symbol,
            exchanges=successful_venues,
            timestamp=int(datetime.utcnow().timestamp() * 1000),
            bids=aggregated_bids,
            asks=aggregated_asks,
            best_bid=best_bid,
            best_ask=best_ask,
            global_mid=global_mid,
            total_bid_depth_usd=total_bid_depth_usd,
            total_ask_depth_usd=total_ask_depth_usd,
        )

        return agg_orderbook, metas

    async def _fetch_venue_specs(
        self, symbol: str, exchange: Optional[str]
    ) -> Tuple[VenueSpecs, SourceMeta]:
        """获取场所规格（支持Binance和OKX）"""
        exchange = exchange or "binance"

        if exchange == "binance":
            data, meta = await self.binance.get_exchange_info(symbol)
            return VenueSpecs(**data), meta
        elif exchange == "okx":
            if not self.okx:
                raise ValueError("OKX client not configured")
            okx_symbol = self.okx.normalize_symbol(symbol, "spot")
            data, meta = await self.okx.get_exchange_info(okx_symbol)
            return VenueSpecs(**data), meta
        else:
            raise ValueError(f"Unsupported exchange: {exchange}")

    async def _fetch_sector_stats(
        self, symbol: str
    ) -> Tuple[SectorStats, SourceMeta]:
        """
        获取板块统计数据

        Args:
            symbol: 交易对符号（如 BTCUSDT）

        Returns:
            (SectorStats, SourceMeta)
        """
        # 提取基础资产符号（从 BTCUSDT 提取 BTC）
        base_symbol = self._extract_base_symbol(symbol)

        # 获取币种数据以找到其所属分类
        coin_data = await self.coingecko.get_coin_data(base_symbol)
        sector_info = self.coingecko.transform(coin_data, "sector")

        primary_category = sector_info.get("primary_category")
        if not primary_category:
            raise ValueError(f"No category found for {base_symbol}")

        # 获取所有分类数据
        categories, meta = await self.coingecko.get_categories()

        # 找到匹配的分类
        matching_category = None
        for category in categories:
            if category.get("id") == primary_category or category.get("name") == primary_category:
                matching_category = category
                break

        if not matching_category:
            raise ValueError(f"Category '{primary_category}' not found in CoinGecko categories")

        # 构建 SectorStats
        # 获取top_3_coins（如果有的话）
        top_coins = matching_category.get("top_3_coins", [])
        if isinstance(top_coins, list) and len(top_coins) > 0:
            # CoinGecko返回的可能是对象列表，需要提取symbol
            top_3_symbols = []
            for coin in top_coins[:3]:
                if isinstance(coin, dict):
                    top_3_symbols.append(coin.get("symbol", "").upper())
                elif isinstance(coin, str):
                    top_3_symbols.append(coin.upper())
        else:
            top_3_symbols = None

        sector_stats = SectorStats(
            category_id=matching_category.get("id", ""),
            name=matching_category.get("name", ""),
            market_cap=matching_category.get("market_cap", 0.0),
            market_cap_change_24h=matching_category.get("market_cap_change_24h", 0.0),
            volume_24h=matching_category.get("volume_24h"),
            updated_at=matching_category.get("updated_at"),
            top_3_coins=top_3_symbols,
        )

        return sector_stats, meta

    # ==================== 计算方法 ====================

    def _calculate_volume_profile(
        self, symbol: str, trades: List[TradeData], exchange: str
    ) -> VolumeProfile:
        """计算成交量价格分布"""
        # 转换为字典格式
        trades_dict = [
            {
                "price": t.price,
                "qty": t.qty,
                "side": t.side,
            }
            for t in trades
        ]

        # 确定价格范围和桶大小
        prices = [t.price for t in trades]
        price_range = max(prices) - min(prices)
        bucket_size = price_range / 20  # 分成20个桶

        result = self.vp_calculator.calculate(trades_dict, bucket_size)

        # 时间范围
        time_range_start = min(t.timestamp for t in trades)
        time_range_end = max(t.timestamp for t in trades)

        return VolumeProfile(
            symbol=symbol,
            exchange=exchange,
            time_range_start=time_range_start,
            time_range_end=time_range_end,
            bucket_size=bucket_size,
            buckets=result["buckets"],
            poc_price=result["poc_price"],
            value_area_high=result["value_area_high"],
            value_area_low=result["value_area_low"],
        )

    def _calculate_taker_flow(
        self, symbol: str, trades: List[TradeData], exchange: str
    ) -> TakerFlow:
        """计算主动买卖流"""
        # 转换为字典格式
        trades_dict = [
            {
                "side": t.side,
                "qty": t.qty,
                "quote_qty": t.quote_qty,
            }
            for t in trades
        ]

        result = self.taker_flow_analyzer.analyze(trades_dict)

        # 时间范围
        time_range_start = min(t.timestamp for t in trades)
        time_range_end = max(t.timestamp for t in trades)

        return TakerFlow(
            symbol=symbol,
            exchange=exchange,
            time_range_start=time_range_start,
            time_range_end=time_range_end,
            total_buy_volume=result["total_buy_volume"],
            total_sell_volume=result["total_sell_volume"],
            total_buy_count=result["total_buy_count"],
            total_sell_count=result["total_sell_count"],
            net_volume=result["net_volume"],
            buy_ratio=result["buy_ratio"],
            large_order_threshold=result["large_order_threshold"],
            large_buy_count=result["large_buy_count"],
            large_sell_count=result["large_sell_count"],
        )

    def _estimate_slippage(
        self,
        symbol: str,
        orderbook: OrderbookData,
        current_price: float,
        order_size_usd: float,
        exchange: str,
    ) -> SlippageEstimate:
        """估算滑点"""
        # 转换为字典格式
        orderbook_dict = {
            "bids": [{"price": b.price, "quantity": b.quantity} for b in orderbook.bids],
            "asks": [{"price": a.price, "quantity": a.quantity} for a in orderbook.asks],
        }

        # 估算买入滑点（默认）
        result = self.slippage_estimator.estimate(
            orderbook_dict, order_size_usd, "buy", current_price
        )

        return SlippageEstimate(
            symbol=symbol,
            exchange=exchange,
            side=result["side"],
            order_size_usd=result["order_size_usd"],
            mid_price=result["mid_price"],
            avg_fill_price=result["avg_fill_price"],
            slippage_bps=result["slippage_bps"],
            slippage_usd=result["slippage_usd"],
            filled_quantity=result["filled_quantity"],
            orderbook_depth_sufficient=result["orderbook_depth_sufficient"],
        )

    # ==================== 辅助方法 ====================

    def _normalize_symbol(self, symbol: str) -> str:
        """
        标准化交易对符号为Binance格式

        Args:
            symbol: 输入符号，如 BTC/USDT, BTCUSDT

        Returns:
            标准化符号: BTCUSDT
        """
        # 移除斜杠
        symbol = symbol.replace("/", "").upper()

        # 如果不包含USDT后缀，添加之
        if not symbol.endswith("USDT"):
            symbol = symbol + "USDT"

        return symbol

    def _extract_base_symbol(self, symbol: str) -> str:
        """
        从交易对中提取基础资产符号

        Args:
            symbol: 交易对符号，如 BTCUSDT, BTC/USDT, ETHUSDT

        Returns:
            基础资产符号: BTC, ETH
        """
        # 移除斜杠并转大写
        symbol = symbol.replace("/", "").upper()

        # 常见计价货币后缀
        quote_currencies = ["USDT", "USDC", "BUSD", "USD", "BTC", "ETH", "BNB"]

        # 尝试移除已知的计价货币
        for quote in quote_currencies:
            if symbol.endswith(quote):
                base = symbol[:-len(quote)]
                if base:  # 确保还有剩余的基础资产
                    return base

        # 如果没有匹配，尝试默认移除最后4个字符（假设是USDT）
        if len(symbol) > 4:
            return symbol[:-4]

        # 降级：返回原始符号
        return symbol
