"""
onchain_whale_transfers 工具实现

基于 Whale Alert API 提供大额转账监控数据。
"""
import time
from datetime import datetime, timedelta
from typing import Optional

import structlog

from src.core.models import (
    OnchainWhaleTransfersInput,
    OnchainWhaleTransfersOutput,
    SourceMeta,
)
from src.data_sources.whale_alert import WhaleAlertClient

logger = structlog.get_logger()


class OnchainWhaleTransfersTool:
    """onchain_whale_transfers 工具"""

    def __init__(self, whale_alert_client: Optional[WhaleAlertClient] = None):
        self.whale_alert = whale_alert_client or WhaleAlertClient()
        logger.info("onchain_whale_transfers_tool_initialized")

    async def execute(
        self, params: OnchainWhaleTransfersInput
    ) -> OnchainWhaleTransfersOutput:
        start_time = time.time()
        logger.info(
            "onchain_whale_transfers_execute_start",
            token_symbol=params.token_symbol,
            min_value_usd=params.min_value_usd,
            lookback_hours=params.lookback_hours,
        )

        warnings: list[str] = []
        source_metas: list[SourceMeta] = []

        end_time = int(datetime.utcnow().timestamp())
        start_ts = int(
            (datetime.utcnow() - timedelta(hours=params.lookback_hours)).timestamp()
        )

        whale_data, meta = await self.whale_alert.get_transactions(
            min_value=int(params.min_value_usd),
            start_time=start_ts,
            end_time=end_time,
            currency=params.token_symbol.lower() if params.token_symbol else None,
            limit=100,
        )
        source_metas.append(meta)

        elapsed = time.time() - start_time
        logger.info(
            "onchain_whale_transfers_execute_complete",
            token_symbol=params.token_symbol,
            elapsed_ms=round(elapsed * 1000, 2),
        )

        return OnchainWhaleTransfersOutput(
            whale_transfers=whale_data,
            source_meta=source_metas,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )

