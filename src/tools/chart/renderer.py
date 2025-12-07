"""
draw_chart 工具实现（接收客户端生成的图表配置）

职责：
- 接收上游 Agent / 客户端已经根据 K 线 / 指标等生成的 Plotly 配置
- 做轻量校验与数据点统计
- 统一输出结构，方便前端直接渲染或持久化

重要说明：
- 本工具不再从其他 MCP 工具（如 market_microstructure）拉取数据，
  由调用方负责数据获取与预处理。
"""
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

from src.core.models import ChartOutput, DrawChartInput, DrawChartOutput

logger = structlog.get_logger()


class DrawChartTool:
    """draw_chart工具（接收并规范化客户端图表配置）"""

    def __init__(self, *args: Any, **kwargs: Any):
        """
        初始化 draw_chart 工具。

        为了兼容旧的构造签名，保留 *args / **kwargs，但不再依赖
        MarketMicrostructureTool 等其他工具。
        """
        logger.info("draw_chart_tool_initialized")

    async def execute(self, params: DrawChartInput) -> DrawChartOutput:
        """执行 draw_chart 查询（不拉取数据，仅验证/包装配置）"""
        start_time = time.time()
        logger.info(
            "draw_chart_execute_start",
            symbol=params.symbol,
            chart_type=params.chart_type,
            timeframe=params.timeframe,
        )

        warnings: List[str] = []

        chart_config = params.config or {}
        data_points = self._infer_data_points(chart_config)

        if data_points == 0:
            warnings.append("No data points detected in chart config.")

        elapsed = time.time() - start_time
        logger.info(
            "draw_chart_execute_complete",
            symbol=params.symbol,
            elapsed_ms=round(elapsed * 1000, 2),
            data_points=data_points,
        )

        return DrawChartOutput(
            symbol=params.symbol,
            chart_type=params.chart_type,
            chart=ChartOutput(
                chart_config=chart_config,
                data_points=data_points,
                warnings=warnings,
            ),
            as_of_utc=datetime.utcnow(),
        )

    @staticmethod
    def _infer_data_points(config: Dict[str, Any]) -> int:
        """
        从 Plotly 配置中推断数据点数量。

        优先使用第一个 trace 的 x/y 长度；若不可用则返回 0。
        """
        try:
            data = config.get("data") or []
            if not data:
                return 0

            first = data[0] or {}
            if isinstance(first, dict):
                for key in ("x", "y", "close", "candles"):
                    series = first.get(key)
                    if isinstance(series, list):
                        return len(series)
        except Exception:
            return 0

        return 0

    def _generate_mock_data(self, symbol: str, timeframe: str) -> List[Dict]:
        """生成mock数据用于演示"""
        import random

        data = []
        base_price = 95000 if "BTC" in symbol.upper() else 3000
        current_time = int(datetime.utcnow().timestamp() * 1000)

        # 生成100个数据点
        for i in range(100):
            # 简单的随机游走
            change = random.uniform(-0.02, 0.02)
            base_price *= (1 + change)

            candle = {
                "time": current_time - (100 - i) * 3600000,  # 1小时间隔
                "open": base_price,
                "high": base_price * (1 + abs(random.uniform(0, 0.01))),
                "low": base_price * (1 - abs(random.uniform(0, 0.01))),
                "close": base_price * (1 + random.uniform(-0.01, 0.01)),
                "volume": random.uniform(100, 1000),
            }
            data.append(candle)

        return data

    def _generate_chart_config(
        self,
        chart_type: str,
        data: List[Dict],
        indicators: List[str],
        symbol: str,
    ) -> Dict[str, Any]:
        """生成Plotly图表配置"""
        if not data:
            return {"data": [], "layout": {}}

        times = [datetime.fromtimestamp(d["time"] / 1000) for d in data]

        if chart_type == "candlestick":
            trace = {
                "type": "candlestick",
                "x": [t.isoformat() for t in times],
                "open": [d["open"] for d in data],
                "high": [d["high"] for d in data],
                "low": [d["low"] for d in data],
                "close": [d["close"] for d in data],
                "name": symbol,
            }
        elif chart_type == "line":
            trace = {
                "type": "scatter",
                "mode": "lines",
                "x": [t.isoformat() for t in times],
                "y": [d["close"] for d in data],
                "name": symbol,
            }
        elif chart_type == "area":
            trace = {
                "type": "scatter",
                "mode": "lines",
                "fill": "tozeroy",
                "x": [t.isoformat() for t in times],
                "y": [d["close"] for d in data],
                "name": symbol,
            }
        elif chart_type == "bar":
            trace = {
                "type": "bar",
                "x": [t.isoformat() for t in times],
                "y": [d["volume"] for d in data],
                "name": "Volume",
            }
        else:
            # 默认折线图
            trace = {
                "type": "scatter",
                "mode": "lines",
                "x": [t.isoformat() for t in times],
                "y": [d["close"] for d in data],
                "name": symbol,
            }

        layout = {
            "title": f"{symbol} - {chart_type.capitalize()} Chart",
            "xaxis": {"title": "Time", "type": "date"},
            "yaxis": {"title": "Price"},
            "hovermode": "x unified",
        }

        return {"data": [trace], "layout": layout}

    def _calculate_indicators(
        self, data: List[Dict], indicators: List[str]
    ) -> List[Dict]:
        """计算技术指标"""
        traces = []

        for indicator in indicators:
            if indicator.lower() == "ma":
                # 简单移动平均线（20期）
                ma_values = self._calculate_ma(
                    [d["close"] for d in data], period=20
                )
                times = [datetime.fromtimestamp(d["time"] / 1000) for d in data]
                traces.append(
                    {
                        "type": "scatter",
                        "mode": "lines",
                        "x": [t.isoformat() for t in times],
                        "y": ma_values,
                        "name": "MA(20)",
                        "line": {"dash": "dash"},
                    }
                )
            elif indicator.lower() == "rsi":
                # RSI指标（需要单独的子图）
                rsi_values = self._calculate_rsi([d["close"] for d in data])
                times = [datetime.fromtimestamp(d["time"] / 1000) for d in data]
                traces.append(
                    {
                        "type": "scatter",
                        "mode": "lines",
                        "x": [t.isoformat() for t in times],
                        "y": rsi_values,
                        "name": "RSI(14)",
                        "yaxis": "y2",
                    }
                )

        return traces

    @staticmethod
    def _calculate_ma(prices: List[float], period: int = 20) -> List[Optional[float]]:
        """计算移动平均线"""
        ma = []
        for i in range(len(prices)):
            if i < period - 1:
                ma.append(None)
            else:
                avg = sum(prices[i - period + 1 : i + 1]) / period
                ma.append(avg)
        return ma

    @staticmethod
    def _calculate_rsi(prices: List[float], period: int = 14) -> List[Optional[float]]:
        """计算RSI指标"""
        if len(prices) < period + 1:
            return [None] * len(prices)

        rsi_values = [None] * period

        # 计算价格变化
        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

        # 分离涨跌
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        # 计算初始平均涨跌
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        # 计算RSI
        for i in range(period, len(prices)):
            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            rsi_values.append(rsi)

            # 更新平均值（使用Wilder's smoothing）
            if i < len(deltas):
                avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        return rsi_values
