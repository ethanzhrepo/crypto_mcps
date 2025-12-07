"""
onchain_token_unlocks 工具实现

基于 Token Unlocks API 提供代币解锁计划数据。
"""
import time
from datetime import datetime
from typing import Optional

import structlog

from src.core.models import (
    OnchainTokenUnlocksInput,
    OnchainTokenUnlocksOutput,
    SourceMeta,
)
from src.data_sources.token_unlocks import TokenUnlocksClient

logger = structlog.get_logger()


class OnchainTokenUnlocksTool:
    """onchain_token_unlocks 工具"""

    def __init__(self, token_unlocks_client: Optional[TokenUnlocksClient] = None):
        self.token_unlocks = token_unlocks_client or TokenUnlocksClient()
        logger.info("onchain_token_unlocks_tool_initialized")

    async def execute(
        self, params: OnchainTokenUnlocksInput
    ) -> OnchainTokenUnlocksOutput:
        start_time = time.time()
        logger.info(
            "onchain_token_unlocks_execute_start",
            token_symbol=params.token_symbol,
        )

        warnings: list[str] = []
        source_metas: list[SourceMeta] = []

        unlocks, meta = await self.token_unlocks.get_upcoming_unlocks(
            token_symbol=params.token_symbol,
            days_ahead=30,
            limit=50,
        )
        source_metas.append(meta)

        elapsed = time.time() - start_time
        logger.info(
            "onchain_token_unlocks_execute_complete",
            token_symbol=params.token_symbol,
            elapsed_ms=round(elapsed * 1000, 2),
        )

        return OnchainTokenUnlocksOutput(
            token_unlocks=unlocks,
            source_meta=source_metas,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )

