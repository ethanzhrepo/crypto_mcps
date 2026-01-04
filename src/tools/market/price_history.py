"""
price_history 工具

获取加密货币的历史K线数据，并计算常用技术指标。
用于支持技术分析、波动率计算和投资决策。
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import structlog

from src.core.models import (
    OHLCVData,
    PriceHistoryIncludeIndicator,
    PriceHistoryIndicators,
    PriceHistoryInput,
    PriceHistoryOutput,
    PriceHistoryStatistics,
    SourceMeta,
    SupportResistance,
)
from src.data_sources.binance import BinanceClient
from src.data_sources.okx import OKXClient
from src.tools.market.indicators import (
    calculate_atr,
    calculate_bollinger,
    calculate_ema,
    calculate_macd,
    calculate_max_drawdown,
    calculate_price_changes,
    calculate_rsi,
    calculate_sharpe_ratio,
    calculate_sma,
    calculate_volatility,
    find_support_resistance,
)

logger = structlog.get_logger()


class PriceHistoryTool:
    """
    历史价格与技术指标工具
    
    数据源优先级:
    1. Binance (主源) - 数据完整，免费
    2. OKX (备源) - 免费备选
    """
    
    # Binance interval mapping
    INTERVAL_MAP = {
        "1h": "1h",
        "4h": "4h",
        "1d": "1d",
        "1w": "1w",
        "1M": "1M",
    }
    
    # 每个周期的毫秒数
    INTERVAL_MS = {
        "1h": 3600 * 1000,
        "4h": 4 * 3600 * 1000,
        "1d": 24 * 3600 * 1000,
        "1w": 7 * 24 * 3600 * 1000,
        "1M": 30 * 24 * 3600 * 1000,
    }
    
    def __init__(
        self,
        binance_client: BinanceClient,
        okx_client: Optional[OKXClient] = None,
    ):
        self.binance = binance_client
        self.okx = okx_client
        logger.info("price_history_tool_initialized")
    
    async def execute(
        self, params: Union[PriceHistoryInput, Dict[str, Any]]
    ) -> PriceHistoryOutput:
        """
        执行历史价格查询和技术指标计算
        
        Args:
            params: 输入参数
            
        Returns:
            PriceHistoryOutput
        """
        if isinstance(params, dict):
            params = PriceHistoryInput(**params)
        
        logger.info(
            "price_history_execute_start",
            symbol=params.symbol,
            interval=params.interval,
            lookback_days=params.lookback_days,
        )
        
        warnings: List[str] = []
        source_meta: List[SourceMeta] = []
        
        # 1. 获取K线数据
        ohlcv_data, meta = await self._fetch_klines(
            symbol=params.symbol,
            interval=params.interval,
            lookback_days=params.lookback_days,
        )
        source_meta.append(meta)
        
        if not ohlcv_data:
            warnings.append("No OHLCV data available")
            return self._empty_response(params, warnings, source_meta)
        
        # 2. 提取价格数组
        closes = [candle.close for candle in ohlcv_data]
        highs = [candle.high for candle in ohlcv_data]
        lows = [candle.low for candle in ohlcv_data]
        
        # 3. 计算技术指标
        indicators = self._calculate_indicators(
            closes=closes,
            highs=highs,
            lows=lows,
            include_indicators=params.include_indicators,
            indicator_params=params.indicator_params,
        )
        
        # 4. 计算统计指标
        statistics = self._calculate_statistics(closes)
        
        # 5. 查找支撑/阻力位
        support_levels, resistance_levels = find_support_resistance(
            closes=closes, highs=highs, lows=lows
        )
        
        # 6. 构建输出
        date_range = {
            "start": datetime.utcfromtimestamp(ohlcv_data[0].timestamp / 1000).isoformat() + "Z",
            "end": datetime.utcfromtimestamp(ohlcv_data[-1].timestamp / 1000).isoformat() + "Z",
        }
        
        output = PriceHistoryOutput(
            symbol=params.symbol,
            interval=params.interval,
            data_points=len(ohlcv_data),
            date_range=date_range,
            ohlcv=ohlcv_data,
            indicators=indicators,
            statistics=statistics,
            support_resistance=SupportResistance(
                support_levels=support_levels,
                resistance_levels=resistance_levels,
            ),
            source_meta=source_meta,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )
        
        logger.info(
            "price_history_execute_complete",
            symbol=params.symbol,
            data_points=len(ohlcv_data),
        )
        
        return output
    
    async def _fetch_klines(
        self,
        symbol: str,
        interval: str,
        lookback_days: int,
    ) -> tuple[List[OHLCVData], SourceMeta]:
        """从交易所获取K线数据"""
        
        # 格式化symbol (BTC/USDT -> BTCUSDT)
        formatted_symbol = symbol.replace("/", "").upper()
        
        # 计算需要的K线数量
        interval_ms = self.INTERVAL_MS.get(interval, self.INTERVAL_MS["1d"])
        total_ms = lookback_days * 24 * 3600 * 1000
        limit = min(int(total_ms / interval_ms) + 1, 1000)  # Binance max 1000
        
        try:
            # 使用Binance获取数据
            raw_klines, meta = await self.binance.get_klines(
                symbol=formatted_symbol,
                interval=self.INTERVAL_MAP.get(interval, "1d"),
                limit=limit,
                market="spot",
            )
            
            # 转换为OHLCVData格式
            ohlcv_data = []
            for kline in raw_klines:
                ohlcv_data.append(OHLCVData(
                    timestamp=kline["open_time"],
                    open=kline["open"],
                    high=kline["high"],
                    low=kline["low"],
                    close=kline["close"],
                    volume=kline["volume"],
                ))
            
            return ohlcv_data, meta
            
        except Exception as e:
            logger.warning(f"Binance klines fetch failed: {e}")
            
            # 尝试OKX备源
            if self.okx:
                try:
                    # OKX implementation would go here
                    pass
                except Exception as okx_e:
                    logger.warning(f"OKX klines fetch also failed: {okx_e}")
            
            # 返回空数据
            return [], SourceMeta(
                provider="binance",
                endpoint="/api/v3/klines",
                as_of_utc=datetime.utcnow().isoformat() + "Z",
                ttl_seconds=3600,
                degraded=True,
            )
    
    def _calculate_indicators(
        self,
        closes: List[float],
        highs: List[float],
        lows: List[float],
        include_indicators: List[PriceHistoryIncludeIndicator],
        indicator_params: Optional[Dict[str, Any]] = None,
    ) -> PriceHistoryIndicators:
        """计算技术指标"""
        
        indicator_params = indicator_params or {}
        
        # 检查是否包含 ALL
        include_all = PriceHistoryIncludeIndicator.ALL in include_indicators
        
        indicators = PriceHistoryIndicators()
        
        # SMA
        if include_all or PriceHistoryIncludeIndicator.SMA in include_indicators:
            sma_periods = indicator_params.get("sma_periods", [20, 50, 200])
            indicators.sma = calculate_sma(closes, sma_periods)
        
        # EMA
        if include_all or PriceHistoryIncludeIndicator.EMA in include_indicators:
            ema_periods = indicator_params.get("ema_periods", [12, 26])
            indicators.ema = calculate_ema(closes, ema_periods)
        
        # RSI
        if include_all or PriceHistoryIncludeIndicator.RSI in include_indicators:
            rsi_period = indicator_params.get("rsi_period", 14)
            indicators.rsi = calculate_rsi(closes, rsi_period)
        
        # MACD
        if include_all or PriceHistoryIncludeIndicator.MACD in include_indicators:
            macd_fast = indicator_params.get("macd_fast", 12)
            macd_slow = indicator_params.get("macd_slow", 26)
            macd_signal = indicator_params.get("macd_signal", 9)
            indicators.macd = calculate_macd(closes, macd_fast, macd_slow, macd_signal)
        
        # Bollinger Bands
        if include_all or PriceHistoryIncludeIndicator.BOLLINGER in include_indicators:
            bb_period = indicator_params.get("bollinger_period", 20)
            bb_std = indicator_params.get("bollinger_std", 2.0)
            indicators.bollinger = calculate_bollinger(closes, bb_period, bb_std)
        
        # ATR
        if include_all or PriceHistoryIncludeIndicator.ATR in include_indicators:
            atr_period = indicator_params.get("atr_period", 14)
            indicators.atr = calculate_atr(highs, lows, closes, atr_period)
        
        return indicators
    
    def _calculate_statistics(self, closes: List[float]) -> PriceHistoryStatistics:
        """计算统计指标"""
        
        # 价格变化
        price_changes = calculate_price_changes(closes)
        
        return PriceHistoryStatistics(
            volatility_30d=calculate_volatility(closes, 30),
            volatility_90d=calculate_volatility(closes, 90),
            max_drawdown_30d=calculate_max_drawdown(closes, 30),
            max_drawdown_90d=calculate_max_drawdown(closes, 90),
            sharpe_ratio_90d=calculate_sharpe_ratio(closes, 90),
            current_vs_ath_pct=price_changes.get("current_vs_ath_pct"),
            current_vs_atl_pct=price_changes.get("current_vs_atl_pct"),
            price_change_7d_pct=price_changes.get("price_change_7d_pct"),
            price_change_30d_pct=price_changes.get("price_change_30d_pct"),
            price_change_90d_pct=price_changes.get("price_change_90d_pct"),
        )
    
    def _empty_response(
        self,
        params: PriceHistoryInput,
        warnings: List[str],
        source_meta: List[SourceMeta],
    ) -> PriceHistoryOutput:
        """返回空响应"""
        
        return PriceHistoryOutput(
            symbol=params.symbol,
            interval=params.interval,
            data_points=0,
            date_range={"start": "", "end": ""},
            ohlcv=[],
            indicators=PriceHistoryIndicators(),
            statistics=PriceHistoryStatistics(),
            support_resistance=SupportResistance(),
            source_meta=source_meta,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )


__all__ = ["PriceHistoryTool"]
