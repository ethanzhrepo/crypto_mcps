"""
onchain_stablecoins_cex 工具实现

提供稳定币指标与 CEX 储备聚合：
- 稳定币：前若干主要稳定币的供应与链上分布
- CEX 储备：指定或全部交易所的储备结构
"""
import time
from datetime import datetime
from typing import Optional

import structlog

from src.core.models import (
    CEXReservesData,
    OnchainStablecoinsCEXInput,
    OnchainStablecoinsCEXOutput,
    SourceMeta,
    StablecoinMetrics,
)
from src.data_sources.defillama import DefiLlamaClient

logger = structlog.get_logger()


class OnchainStablecoinsCEXTool:
    """onchain_stablecoins_cex 工具"""

    def __init__(self, defillama_client: Optional[DefiLlamaClient] = None):
        self.defillama = defillama_client or DefiLlamaClient()
        logger.info("onchain_stablecoins_cex_tool_initialized")

    async def execute(
        self, params: OnchainStablecoinsCEXInput
    ) -> OnchainStablecoinsCEXOutput:
        start_time = time.time()
        logger.info(
            "onchain_stablecoins_cex_execute_start",
            exchange=params.exchange,
        )

        warnings: list[str] = []
        source_metas: list[SourceMeta] = []

        stablecoin_metrics: list[StablecoinMetrics] = []
        cex_reserves: Optional[CEXReservesData] = None

        # 稳定币
        try:
            stablecoins_data, stablecoins_meta = await self.defillama.get_stablecoins()
            stablecoin_metrics = [StablecoinMetrics(**s) for s in stablecoins_data]
            source_metas.append(stablecoins_meta)
        except Exception as exc:
            logger.warning("Failed to fetch stablecoins from DefiLlama", error=str(exc))
            warnings.append(f"Stablecoins fetch failed: {exc}")

        # CEX 储备
        try:
            cex_raw, cex_meta = await self.defillama.get_cex_reserves(params.exchange)
            cex_reserves = CEXReservesData(**cex_raw)
            source_metas.append(cex_meta)
        except Exception as exc:
            logger.warning("Failed to fetch CEX reserves from DefiLlama", error=str(exc))
            warnings.append(f"CEX reserves fetch failed: {exc}")

        elapsed = time.time() - start_time
        logger.info(
            "onchain_stablecoins_cex_execute_complete",
            exchange=params.exchange,
            elapsed_ms=round(elapsed * 1000, 2),
            warnings=len(warnings),
        )

        return OnchainStablecoinsCEXOutput(
            stablecoin_metrics=stablecoin_metrics,
            cex_reserves=cex_reserves,
            source_meta=source_metas,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )

