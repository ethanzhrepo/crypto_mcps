"""
etf_flows_holdings tool implementation.
"""
import time
from datetime import datetime
from typing import Optional

import structlog

from src.core.models import (
    EtfFlowRecord,
    EtfFlowsHoldingsInput,
    EtfFlowsHoldingsOutput,
    EtfHoldingRecord,
    SourceMeta,
)
from src.data_sources.farside import FarsideEtfClient

logger = structlog.get_logger()


class EtfFlowsHoldingsTool:
    """ETF flows + holdings tool."""

    def __init__(self, farside_client: Optional[FarsideEtfClient] = None):
        self.farside = farside_client or FarsideEtfClient()
        logger.info("etf_flows_holdings_tool_initialized")

    async def execute(self, params) -> EtfFlowsHoldingsOutput:
        if isinstance(params, dict):
            params = EtfFlowsHoldingsInput(**params)

        start_time = time.time()
        warnings: list[str] = []
        source_metas: list[SourceMeta] = []
        flows: list[EtfFlowRecord] = []
        holdings: list[EtfHoldingRecord] = []

        include_all = "all" in [f.value for f in params.include_fields]
        include_flows = include_all or any(f.value == "flows" for f in params.include_fields)
        include_holdings = include_all or any(f.value == "holdings" for f in params.include_fields)

        if include_flows:
            try:
                parsed, meta = await self.farside.get_etf_flows(
                    dataset=params.dataset,
                    url_override=params.url_override,
                )
                source_metas.append(meta)
                for row in parsed.get("rows", []):
                    flows.append(EtfFlowRecord(data=row))
            except Exception as exc:
                logger.warning("etf_flows_fetch_failed", error=str(exc))
                warnings.append(f"ETF flows fetch failed: {exc}")

        if include_holdings:
            warnings.append("ETF holdings data source not configured; returning empty holdings.")

        elapsed = time.time() - start_time
        logger.info(
            "etf_flows_holdings_execute_complete",
            dataset=params.dataset,
            elapsed_ms=round(elapsed * 1000, 2),
        )

        return EtfFlowsHoldingsOutput(
            dataset=params.dataset,
            flows=flows,
            holdings=holdings,
            source_meta=source_metas,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )
