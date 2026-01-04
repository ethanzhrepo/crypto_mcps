"""
cex_netflow_reserves tool implementation.
"""
import time
from datetime import datetime, timedelta
from typing import Optional

import structlog

from src.core.models import (
    CexNetflowReservesInput,
    CexNetflowReservesOutput,
    SourceMeta,
    WhaleTransfersData,
)
from src.data_sources.defillama import DefiLlamaClient
from src.data_sources.whale_alert import WhaleAlertClient
from src.utils.config import config

logger = structlog.get_logger()


class CexNetflowReservesTool:
    """CEX netflow + reserves tool."""

    def __init__(
        self,
        defillama_client: Optional[DefiLlamaClient] = None,
        whale_alert_client: Optional[WhaleAlertClient] = None,
    ):
        self.defillama = defillama_client or DefiLlamaClient()
        self.whale_alert = whale_alert_client
        logger.info("cex_netflow_reserves_tool_initialized")

    async def execute(self, params) -> CexNetflowReservesOutput:
        if isinstance(params, dict):
            params = CexNetflowReservesInput(**params)

        start_time = time.time()
        warnings: list[str] = []
        source_metas: list[SourceMeta] = []

        reserves_data: dict = {}
        whale_transfers: Optional[WhaleTransfersData] = None

        try:
            reserves_data, meta = await self.defillama.get_cex_reserves(params.exchange)
            source_metas.append(meta)
        except Exception as exc:
            logger.warning("cex_reserves_fetch_failed", error=str(exc))
            warnings.append(f"CEX reserves fetch failed: {exc}")

        if params.include_whale_transfers:
            whale_client = self.whale_alert or WhaleAlertClient(api_key=config.get_api_key("whale_alert"))
            try:
                end_time = int(datetime.utcnow().timestamp())
                start_time_ts = int((datetime.utcnow() - timedelta(hours=params.lookback_hours)).timestamp())
                whale_transfers, meta = await whale_client.get_transactions(
                    min_value=params.min_transfer_usd,
                    start_time=start_time_ts,
                    end_time=end_time,
                    currency=None,
                    limit=100,
                )
                source_metas.append(meta)
            except Exception as exc:
                logger.warning("whale_alert_fetch_failed", error=str(exc))
                warnings.append(f"Whale Alert fetch failed: {exc}")

        elapsed = time.time() - start_time
        logger.info(
            "cex_netflow_reserves_execute_complete",
            exchange=params.exchange,
            elapsed_ms=round(elapsed * 1000, 2),
        )

        return CexNetflowReservesOutput(
            exchange=params.exchange,
            reserves=reserves_data or {},
            whale_transfers=whale_transfers,
            source_meta=source_metas,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )
