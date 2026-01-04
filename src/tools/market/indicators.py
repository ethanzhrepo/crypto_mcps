"""
技术指标计算模块

使用 pandas-ta 库计算常用技术指标
"""
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False

from src.utils.logger import get_logger

logger = get_logger(__name__)


def calculate_sma(
    closes: List[float], periods: List[int] = [20, 50, 200]
) -> Dict[str, List[Optional[float]]]:
    """
    计算简单移动平均线 (SMA)
    
    Args:
        closes: 收盘价列表
        periods: SMA周期列表
        
    Returns:
        {sma_20: [...], sma_50: [...], sma_200: [...]}
    """
    df = pd.DataFrame({"close": closes})
    result = {}
    
    for period in periods:
        if HAS_PANDAS_TA:
            sma = ta.sma(df["close"], length=period)
        else:
            sma = df["close"].rolling(window=period).mean()
        result[f"sma_{period}"] = [None if pd.isna(v) else round(v, 2) for v in sma.tolist()]
    
    return result


def calculate_ema(
    closes: List[float], periods: List[int] = [12, 26]
) -> Dict[str, List[Optional[float]]]:
    """
    计算指数移动平均线 (EMA)
    
    Args:
        closes: 收盘价列表
        periods: EMA周期列表
        
    Returns:
        {ema_12: [...], ema_26: [...]}
    """
    df = pd.DataFrame({"close": closes})
    result = {}
    
    for period in periods:
        if HAS_PANDAS_TA:
            ema = ta.ema(df["close"], length=period)
        else:
            ema = df["close"].ewm(span=period, adjust=False).mean()
        result[f"ema_{period}"] = [None if pd.isna(v) else round(v, 2) for v in ema.tolist()]
    
    return result


def calculate_rsi(
    closes: List[float], period: int = 14
) -> Dict[str, Any]:
    """
    计算相对强弱指数 (RSI)
    
    Args:
        closes: 收盘价列表
        period: RSI周期
        
    Returns:
        {rsi_14: [...], current: float}
    """
    df = pd.DataFrame({"close": closes})
    
    if HAS_PANDAS_TA:
        rsi = ta.rsi(df["close"], length=period)
    else:
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
    
    rsi_values = [None if pd.isna(v) else round(v, 2) for v in rsi.tolist()]
    current = rsi_values[-1] if rsi_values and rsi_values[-1] is not None else None
    
    return {
        f"rsi_{period}": rsi_values,
        "current": current,
    }


def calculate_macd(
    closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> Dict[str, Any]:
    """
    计算MACD指标
    
    Args:
        closes: 收盘价列表
        fast: 快线周期
        slow: 慢线周期
        signal: 信号线周期
        
    Returns:
        {macd_line: [...], signal_line: [...], histogram: [...], current_signal: str}
    """
    df = pd.DataFrame({"close": closes})
    
    if HAS_PANDAS_TA:
        macd_df = ta.macd(df["close"], fast=fast, slow=slow, signal=signal)
        if macd_df is not None and not macd_df.empty:
            macd_line = macd_df.iloc[:, 0].tolist()
            histogram = macd_df.iloc[:, 1].tolist()
            signal_line = macd_df.iloc[:, 2].tolist()
        else:
            macd_line, signal_line, histogram = [], [], []
    else:
        ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
        macd_line = (ema_fast - ema_slow).tolist()
        signal_series = pd.Series(macd_line).ewm(span=signal, adjust=False).mean()
        signal_line = signal_series.tolist()
        histogram = [(m - s) if m is not None and s is not None else None 
                     for m, s in zip(macd_line, signal_line)]
    
    # Clean up values
    macd_line = [None if (v is None or pd.isna(v)) else round(v, 4) for v in macd_line]
    signal_line = [None if (v is None or pd.isna(v)) else round(v, 4) for v in signal_line]
    histogram = [None if (v is None or pd.isna(v)) else round(v, 4) for v in histogram]
    
    # Determine current signal
    current_signal = "neutral"
    if len(histogram) >= 2:
        current_hist = histogram[-1]
        prev_hist = histogram[-2]
        if current_hist is not None and prev_hist is not None:
            if current_hist > 0 and current_hist > prev_hist:
                current_signal = "bullish"
            elif current_hist < 0 and current_hist < prev_hist:
                current_signal = "bearish"
            elif current_hist > prev_hist:
                current_signal = "bullish_crossover"
            elif current_hist < prev_hist:
                current_signal = "bearish_crossover"
    
    return {
        "macd_line": macd_line,
        "signal_line": signal_line,
        "histogram": histogram,
        "current_signal": current_signal,
    }


def calculate_bollinger(
    closes: List[float], period: int = 20, std_dev: float = 2.0
) -> Dict[str, Any]:
    """
    计算布林带
    
    Args:
        closes: 收盘价列表
        period: 周期
        std_dev: 标准差倍数
        
    Returns:
        {upper: [...], middle: [...], lower: [...], bandwidth: float, percent_b: float}
    """
    df = pd.DataFrame({"close": closes})
    
    if HAS_PANDAS_TA:
        bb = ta.bbands(df["close"], length=period, std=std_dev)
        if bb is not None and not bb.empty:
            lower = bb.iloc[:, 0].tolist()
            middle = bb.iloc[:, 1].tolist()
            upper = bb.iloc[:, 2].tolist()
            bandwidth = bb.iloc[:, 3].tolist() if bb.shape[1] > 3 else None
            percent_b = bb.iloc[:, 4].tolist() if bb.shape[1] > 4 else None
        else:
            lower, middle, upper = [], [], []
            bandwidth, percent_b = None, None
    else:
        middle = df["close"].rolling(window=period).mean()
        std = df["close"].rolling(window=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        lower = lower.tolist()
        middle = middle.tolist()
        upper = upper.tolist()
        bandwidth = None
        percent_b = None
    
    # Clean up values
    upper = [None if (v is None or pd.isna(v)) else round(v, 2) for v in upper]
    middle = [None if (v is None or pd.isna(v)) else round(v, 2) for v in middle]
    lower = [None if (v is None or pd.isna(v)) else round(v, 2) for v in lower]
    
    # Calculate current bandwidth
    current_bandwidth = None
    if len(upper) > 0 and len(middle) > 0 and len(lower) > 0:
        last_upper = upper[-1]
        last_middle = middle[-1]
        last_lower = lower[-1]
        if all(v is not None for v in [last_upper, last_middle, last_lower]) and last_middle > 0:
            current_bandwidth = round((last_upper - last_lower) / last_middle, 4)
    
    return {
        "upper": upper,
        "middle": middle,
        "lower": lower,
        "bandwidth": current_bandwidth,
    }


def calculate_atr(
    highs: List[float], lows: List[float], closes: List[float], period: int = 14
) -> Dict[str, Any]:
    """
    计算平均真实波幅 (ATR)
    
    Args:
        highs: 最高价列表
        lows: 最低价列表
        closes: 收盘价列表
        period: ATR周期
        
    Returns:
        {atr_14: [...], current: float}
    """
    df = pd.DataFrame({"high": highs, "low": lows, "close": closes})
    
    if HAS_PANDAS_TA:
        atr = ta.atr(df["high"], df["low"], df["close"], length=period)
    else:
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
    
    atr_values = [None if pd.isna(v) else round(v, 2) for v in atr.tolist()]
    current = atr_values[-1] if atr_values and atr_values[-1] is not None else None
    
    return {
        f"atr_{period}": atr_values,
        "current": current,
    }


def calculate_volatility(closes: List[float], window: int = 30) -> Optional[float]:
    """
    计算年化波动率
    
    Args:
        closes: 收盘价列表
        window: 窗口大小（天数）
        
    Returns:
        年化波动率（小数形式，如0.45表示45%）
    """
    if len(closes) < window + 1:
        return None
    
    df = pd.DataFrame({"close": closes})
    returns = df["close"].pct_change().dropna()
    
    if len(returns) < window:
        return None
    
    recent_returns = returns.tail(window)
    daily_vol = recent_returns.std()
    annual_vol = daily_vol * math.sqrt(365)
    
    return round(annual_vol, 4) if not pd.isna(annual_vol) else None


def calculate_max_drawdown(closes: List[float], window: Optional[int] = None) -> Optional[float]:
    """
    计算最大回撤
    
    Args:
        closes: 收盘价列表
        window: 窗口大小（可选，None表示全部数据）
        
    Returns:
        最大回撤（负数，如-0.15表示-15%）
    """
    if len(closes) < 2:
        return None
    
    prices = closes[-window:] if window else closes
    df = pd.DataFrame({"close": prices})
    
    cummax = df["close"].cummax()
    drawdown = (df["close"] - cummax) / cummax
    max_dd = drawdown.min()
    
    return round(max_dd, 4) if not pd.isna(max_dd) else None


def calculate_sharpe_ratio(
    closes: List[float], window: int = 90, risk_free_rate: float = 0.05
) -> Optional[float]:
    """
    计算夏普比率
    
    Args:
        closes: 收盘价列表
        window: 窗口大小（天数）
        risk_free_rate: 年化无风险利率
        
    Returns:
        夏普比率
    """
    if len(closes) < window + 1:
        return None
    
    df = pd.DataFrame({"close": closes})
    returns = df["close"].pct_change().dropna()
    
    if len(returns) < window:
        return None
    
    recent_returns = returns.tail(window)
    
    # 年化收益率
    mean_daily_return = recent_returns.mean()
    annual_return = mean_daily_return * 365
    
    # 年化波动率
    daily_vol = recent_returns.std()
    annual_vol = daily_vol * math.sqrt(365)
    
    if annual_vol == 0:
        return None
    
    sharpe = (annual_return - risk_free_rate) / annual_vol
    
    return round(sharpe, 2) if not pd.isna(sharpe) else None


def find_support_resistance(
    closes: List[float],
    highs: Optional[List[float]] = None,
    lows: Optional[List[float]] = None,
    num_levels: int = 3,
) -> Tuple[List[float], List[float]]:
    """
    查找支撑和阻力位
    
    使用局部极值点方法
    
    Args:
        closes: 收盘价列表
        highs: 最高价列表（可选）
        lows: 最低价列表（可选）
        num_levels: 返回的支撑/阻力位数量
        
    Returns:
        (support_levels, resistance_levels) 均为从近到远排序
    """
    if len(closes) < 20:
        return [], []
    
    current_price = closes[-1]
    
    # 使用收盘价或高低价
    prices_high = highs if highs else closes
    prices_low = lows if lows else closes
    
    df = pd.DataFrame({
        "high": prices_high,
        "low": prices_low,
        "close": closes
    })
    
    # 找局部极大值（阻力）
    resistance_candidates = []
    for i in range(5, len(df) - 5):
        if df["high"].iloc[i] == df["high"].iloc[i-5:i+6].max():
            resistance_candidates.append(df["high"].iloc[i])
    
    # 找局部极小值（支撑）
    support_candidates = []
    for i in range(5, len(df) - 5):
        if df["low"].iloc[i] == df["low"].iloc[i-5:i+6].min():
            support_candidates.append(df["low"].iloc[i])
    
    # 过滤：阻力位在当前价格上方，支撑位在当前价格下方
    resistance_levels = sorted(
        [r for r in resistance_candidates if r > current_price],
        key=lambda x: x
    )[:num_levels]
    
    support_levels = sorted(
        [s for s in support_candidates if s < current_price],
        key=lambda x: -x
    )[:num_levels]
    
    # 四舍五入
    resistance_levels = [round(r, 2) for r in resistance_levels]
    support_levels = [round(s, 2) for s in support_levels]
    
    return support_levels, resistance_levels


def calculate_price_changes(
    closes: List[float]
) -> Dict[str, Optional[float]]:
    """
    计算价格变化百分比
    
    Args:
        closes: 收盘价列表
        
    Returns:
        {price_change_7d_pct, price_change_30d_pct, price_change_90d_pct, 
         current_vs_ath_pct, current_vs_atl_pct}
    """
    if not closes:
        return {}
    
    current = closes[-1]
    result = {}
    
    # 7日变化
    if len(closes) >= 7:
        old_price = closes[-7]
        if old_price > 0:
            result["price_change_7d_pct"] = round((current - old_price) / old_price * 100, 2)
    
    # 30日变化
    if len(closes) >= 30:
        old_price = closes[-30]
        if old_price > 0:
            result["price_change_30d_pct"] = round((current - old_price) / old_price * 100, 2)
    
    # 90日变化
    if len(closes) >= 90:
        old_price = closes[-90]
        if old_price > 0:
            result["price_change_90d_pct"] = round((current - old_price) / old_price * 100, 2)
    
    # ATH/ATL计算
    ath = max(closes)
    atl = min(closes)
    
    if ath > 0:
        result["current_vs_ath_pct"] = round((current - ath) / ath * 100, 2)
    
    if atl > 0:
        result["current_vs_atl_pct"] = round((current - atl) / atl * 100, 2)
    
    return result
