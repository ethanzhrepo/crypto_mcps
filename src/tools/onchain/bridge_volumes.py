"""
onchain_bridge_volumes 工具实现

提供跨链桥交易量数据：
- 单个桥或全部桥的 24h / 7d / 30d 交易量
"""
import time
from datetime import datetime
from typing import Optional

import structlog

from src.core.models import (
    BridgeVolumeData,
    OnchainBridgeVolumesInput,
    OnchainBridgeVolumesOutput,
    SourceMeta,
)
from src.data_sources.defillama import DefiLlamaClient

logger = structlog.get_logger()


class OnchainBridgeVolumesTool:
    """onchain_bridge_volumes 工具"""

    def __init__(self, defillama_client: Optional[DefiLlamaClient] = None):
        self.defillama = defillama_client or DefiLlamaClient()
        logger.info("onchain_bridge_volumes_tool_initialized")

    async def execute(
        self, params: OnchainBridgeVolumesInput
    ) -> OnchainBridgeVolumesOutput:
        start_time = time.time()
        logger.info(
            "onchain_bridge_volumes_execute_start",
            bridge=params.bridge,
        )

        warnings: list[str] = []
        source_metas: list[SourceMeta] = []

        bridge_data_raw, meta = await self.defillama.get_bridge_volumes(params.bridge)
        source_metas.append(meta)

        bridge_volumes = BridgeVolumeData(**bridge_data_raw)

        elapsed = time.time() - start_time
        logger.info(
            "onchain_bridge_volumes_execute_complete",
            bridge=params.bridge,
            elapsed_ms=round(elapsed * 1000, 2),
        )

        return OnchainBridgeVolumesOutput(
            bridge_volumes=bridge_volumes,
            source_meta=source_metas,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )

