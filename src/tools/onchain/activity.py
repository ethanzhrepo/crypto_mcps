"""
onchain_activity 工具实现

基于 Etherscan 系列 API 提供链上 activity 指标。
"""
import time
from datetime import datetime

import structlog

from src.core.models import (
    OnchainActivity,
    OnchainActivityInput,
    OnchainActivityOutput,
    SourceMeta,
)
from src.data_sources.etherscan import EtherscanClient
from src.utils.config import config

logger = structlog.get_logger()


class OnchainActivityTool:
    """onchain_activity 工具"""

    def __init__(self):
        logger.info("onchain_activity_tool_initialized")

    async def execute(
        self, params: OnchainActivityInput
    ) -> OnchainActivityOutput:
        start_time = time.time()
        logger.info(
            "onchain_activity_execute_start",
            chain=params.chain,
        )

        warnings: list[str] = []
        source_metas: list[SourceMeta] = []

        api_key = config.get_api_key("etherscan")
        client = EtherscanClient(chain=params.chain, api_key=api_key)

        try:
            activity, meta = await client.get_chain_stats()
            source_metas.append(meta)
        except Exception as exc:
            logger.warning("Failed to fetch chain activity from Etherscan", error=str(exc))
            warnings.append(f"Activity fetch failed: {exc}")
            activity = OnchainActivity(
                protocol=params.protocol,
                chain=params.chain,
                timestamp=datetime.utcnow().isoformat() + "Z",
            )
            from src.core.source_meta import SourceMetaBuilder

            meta = SourceMetaBuilder.build(
                provider=f"etherscan_{params.chain}",
                endpoint="/stats",
                ttl_seconds=300,
            )
            source_metas.append(meta)

        elapsed = time.time() - start_time
        logger.info(
            "onchain_activity_execute_complete",
            chain=params.chain,
            elapsed_ms=round(elapsed * 1000, 2),
            warnings=len(warnings),
        )

        return OnchainActivityOutput(
            activity=activity,
            source_meta=source_metas,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )

