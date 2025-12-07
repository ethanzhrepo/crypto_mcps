"""
onchain_tvl_fees 工具实现

提供协议层 TVL 与费用/收入数据聚合：
- TVL：总锁仓量、链上分布、24h/7d 变化
- 协议费用/收入：24h/7d/30d 维度
"""
import time
from datetime import datetime
from typing import Optional

import structlog

from src.core.models import (
    OnchainTVLFeesInput,
    OnchainTVLFeesOutput,
    ProtocolFeesData,
    TVLData,
)
from src.core.models import SourceMeta
from src.data_sources.defillama import DefiLlamaClient

logger = structlog.get_logger()


class OnchainTVLFeesTool:
    """onchain_tvl_fees 工具"""

    def __init__(self, defillama_client: Optional[DefiLlamaClient] = None):
        """
        初始化 onchain_tvl_fees 工具

        Args:
            defillama_client: DefiLlama 客户端（可选，默认创建新实例）
        """
        self.defillama = defillama_client or DefiLlamaClient()
        logger.info("onchain_tvl_fees_tool_initialized")

    async def execute(self, params: OnchainTVLFeesInput) -> OnchainTVLFeesOutput:
        """
        执行 onchain_tvl_fees 查询。

        Args:
            params: OnchainTVLFeesInput Pydantic 模型

        Returns:
            OnchainTVLFeesOutput
        """
        start_time = time.time()
        logger.info(
            "onchain_tvl_fees_execute_start",
            protocol=params.protocol,
            chain=params.chain,
        )

        warnings: list[str] = []
        source_metas: list[SourceMeta] = []

        tvl: Optional[TVLData] = None
        fees: Optional[ProtocolFeesData] = None

        # TVL
        try:
            tvl_data, tvl_meta = await self.defillama.get_protocol_tvl(
                params.protocol.lower()
            )
            tvl = TVLData(**tvl_data)
            source_metas.append(tvl_meta)
        except Exception as exc:
            logger.warning("Failed to fetch protocol TVL from DefiLlama", error=str(exc))
            warnings.append(f"TVL fetch failed: {exc}")

        # 协议费用
        try:
            fees_data, fees_meta = await self.defillama.get_protocol_fees(
                params.protocol.lower()
            )
            fees = ProtocolFeesData(**fees_data)
            source_metas.append(fees_meta)
        except Exception as exc:
            logger.warning("Failed to fetch protocol fees from DefiLlama", error=str(exc))
            warnings.append(f"Protocol fees fetch failed: {exc}")

        if tvl is None:
            # 即使 TVL 拉取失败，仍尽量返回 fees 数据；协议字段从 fees 或输入中推断
            tvl = TVLData(
                protocol=params.protocol,
                tvl_usd=0.0,
                tvl_change_24h=None,
                tvl_change_7d=None,
                chain_breakdown=None,
                timestamp=datetime.utcnow().isoformat() + "Z",
            )

        if fees is None:
            fees = ProtocolFeesData(
                protocol=params.protocol,
                fees_24h=0.0,
                revenue_24h=0.0,
                fees_7d=0.0,
                revenue_7d=0.0,
                fees_30d=0.0,
                revenue_30d=0.0,
                timestamp=datetime.utcnow().isoformat() + "Z",
            )

        elapsed = time.time() - start_time
        logger.info(
            "onchain_tvl_fees_execute_complete",
            protocol=params.protocol,
            elapsed_ms=round(elapsed * 1000, 2),
            warnings=len(warnings),
        )

        return OnchainTVLFeesOutput(
            protocol=params.protocol,
            chain=params.chain,
            tvl=tvl,
            protocol_fees=fees,
            source_meta=source_metas,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )

