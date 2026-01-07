"""
onchain_analytics 工具实现

基于 CryptoQuant API 提供链上分析指标：
- MVRV: 市值/实现价值比率
- SOPR: 花费产出利润率
- 交易所流量: 储备、净流量、流入/流出
- 矿工数据: 储备、流出
- 资金费率: 永续合约资金费率
"""
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

from src.core.models import SourceMeta
from src.data_sources.cryptoquant import CryptoQuantClient

logger = structlog.get_logger()


class OnchainAnalyticsTool:
    """链上分析工具 (CryptoQuant)"""

    def __init__(self):
        self.client = CryptoQuantClient()
        logger.info("onchain_analytics_tool_initialized")

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行链上分析

        Args:
            params: 输入参数
                - symbol: 资产符号 (BTC, ETH)
                - include_fields: 包含字段列表
                - window: 时间窗口 (hour, day)
                - limit: 数据点数量

        Returns:
            链上分析数据
        """
        start_time = time.time()
        symbol = params.get("symbol", "BTC").upper()
        include_fields = params.get("include_fields", ["all"])
        window = params.get("window", "day")
        limit = params.get("limit", 30)

        logger.info(
            "onchain_analytics_execute_start",
            symbol=symbol,
            include_fields=include_fields,
        )

        warnings: List[str] = []
        source_metas: List[SourceMeta] = []
        data: Dict[str, Any] = {}

        # 判断是否包含字段
        def should_include(field: str) -> bool:
            return "all" in include_fields or field in include_fields

        try:
            # 活跃地址
            if should_include("active_addresses"):
                try:
                    result, meta = await self.client.get_active_addresses(
                        symbol=symbol, window=window, limit=limit
                    )
                    data["active_addresses"] = result
                    source_metas.append(meta)
                except Exception as e:
                    warnings.append(f"Failed to fetch active_addresses: {e}")

            # MVRV
            if should_include("mvrv"):
                try:
                    result, meta = await self.client.get_mvrv_ratio(
                        symbol=symbol, window=window, limit=limit
                    )
                    data["mvrv"] = result
                    source_metas.append(meta)
                except Exception as e:
                    warnings.append(f"Failed to fetch mvrv: {e}")

            # SOPR
            if should_include("sopr"):
                try:
                    result, meta = await self.client.get_sopr(
                        symbol=symbol, window=window, limit=limit
                    )
                    data["sopr"] = result
                    source_metas.append(meta)
                except Exception as e:
                    warnings.append(f"Failed to fetch sopr: {e}")

            # 交易所储备
            if should_include("exchange_reserve"):
                try:
                    result, meta = await self.client.get_exchange_reserve(
                        symbol=symbol, window=window, limit=limit
                    )
                    data["exchange_reserve"] = result
                    source_metas.append(meta)
                except Exception as e:
                    warnings.append(f"Failed to fetch exchange_reserve: {e}")

            # 交易所净流量
            if should_include("exchange_netflow"):
                try:
                    result, meta = await self.client.get_exchange_netflow(
                        symbol=symbol, window=window, limit=limit
                    )
                    data["exchange_netflow"] = result
                    source_metas.append(meta)
                except Exception as e:
                    warnings.append(f"Failed to fetch exchange_netflow: {e}")

            # 矿工数据 (仅 BTC)
            if symbol == "BTC" and should_include("miner"):
                try:
                    reserve, meta1 = await self.client.get_miner_reserve(
                        symbol=symbol, window=window, limit=limit
                    )
                    outflow, meta2 = await self.client.get_miner_outflow(
                        symbol=symbol, window=window, limit=limit
                    )
                    data["miner"] = {
                        "reserve": reserve,
                        "outflow": outflow,
                    }
                    source_metas.extend([meta1, meta2])
                except Exception as e:
                    warnings.append(f"Failed to fetch miner data: {e}")

            # 资金费率
            if should_include("funding_rate"):
                try:
                    result, meta = await self.client.get_funding_rate(
                        symbol=symbol, limit=limit
                    )
                    data["funding_rate"] = result
                    source_metas.append(meta)
                except Exception as e:
                    warnings.append(f"Failed to fetch funding_rate: {e}")

        except Exception as e:
            logger.error("onchain_analytics_execute_error", error=str(e))
            warnings.append(f"Unexpected error: {e}")

        elapsed = time.time() - start_time
        logger.info(
            "onchain_analytics_execute_complete",
            symbol=symbol,
            elapsed_ms=round(elapsed * 1000, 2),
            data_fields=list(data.keys()),
            warnings=len(warnings),
        )

        return {
            "symbol": symbol,
            "data": data,
            "source_meta": [m.model_dump() for m in source_metas],
            "warnings": warnings,
            "as_of_utc": datetime.utcnow().isoformat() + "Z",
        }

    async def close(self):
        """关闭客户端"""
        await self.client.close()


# 工具元数据（用于 MCP 注册）
TOOL_SPEC = {
    "name": "onchain_analytics",
    "description": """链上分析工具 - 提供专业链上分析指标

数据来源: CryptoQuant

支持的指标:
- active_addresses: 活跃地址数（网络使用度）
- mvrv: MVRV比率（市值/实现价值, >3.7超买, <1超卖）
- sopr: SOPR花费产出利润率（>1获利, <1亏损）
- exchange_reserve: 交易所储备量
- exchange_netflow: 交易所净流量（正=流入/看跌, 负=流出/看涨）
- miner: 矿工储备和流出（仅BTC）
- funding_rate: 永续合约资金费率

适用场景:
- 判断市场周期顶底
- 监控资金流向
- 分析持有者行为
- 衍生品杠杆情况""",
    "input_schema": {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "资产符号 (BTC, ETH)",
                "default": "BTC",
            },
            "include_fields": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "all",
                        "active_addresses",
                        "mvrv",
                        "sopr",
                        "exchange_reserve",
                        "exchange_netflow",
                        "miner",
                        "funding_rate",
                    ],
                },
                "description": "要返回的字段列表",
                "default": ["all"],
            },
            "window": {
                "type": "string",
                "enum": ["hour", "day"],
                "description": "时间窗口",
                "default": "day",
            },
            "limit": {
                "type": "integer",
                "description": "历史数据点数量",
                "default": 30,
                "minimum": 1,
                "maximum": 365,
            },
        },
        "required": ["symbol"],
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string"},
            "data": {
                "type": "object",
                "description": "链上分析数据",
            },
            "source_meta": {"type": "array"},
            "warnings": {"type": "array"},
            "as_of_utc": {"type": "string"},
        },
    },
}
