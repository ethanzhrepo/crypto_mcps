"""
lending_liquidation_risk tool implementation.
"""
import time
from datetime import datetime
from typing import Optional

import structlog

from src.core.models import (
    LendingLiquidationRiskInput,
    LendingLiquidationRiskOutput,
    LiquidationsData,
    SourceMeta,
)
from src.data_sources.coinglass import CoinglassClient
from src.data_sources.defillama import DefiLlamaClient
from src.utils.config import config

logger = structlog.get_logger()


class LendingLiquidationRiskTool:
    """Lending + liquidation risk tool."""

    def __init__(
        self,
        defillama_client: Optional[DefiLlamaClient] = None,
        coinglass_client: Optional[CoinglassClient] = None,
    ):
        self.defillama = defillama_client or DefiLlamaClient()
        self.coinglass = coinglass_client
        logger.info("lending_liquidation_risk_tool_initialized")

    async def execute(self, params) -> LendingLiquidationRiskOutput:
        if isinstance(params, dict):
            params = LendingLiquidationRiskInput(**params)

        start_time = time.time()
        warnings: list[str] = []
        source_metas: list[SourceMeta] = []
        yields_data: list[dict] = []
        liquidation_data: Optional[LiquidationsData] = None

        try:
            raw_yields, meta = await self.defillama.get_yields(
                symbol=params.asset,
                protocol=params.protocols[0] if params.protocols else None,
            )
            source_metas.append(meta)
            yields_data = raw_yields
            if params.protocols:
                protocols_lower = {p.lower() for p in params.protocols}
                yields_data = [
                    y for y in yields_data
                    if str(y.get("protocol", "")).lower() in protocols_lower
                ]
        except Exception as exc:
            logger.warning("defillama_yields_fetch_failed", error=str(exc))
            warnings.append(f"DefiLlama yields fetch failed: {exc}")

        if params.include_liquidations:
            if not params.asset:
                warnings.append("Liquidations requested but no asset symbol provided.")
            else:
                coinglass = self.coinglass or CoinglassClient(api_key=config.get_api_key("coinglass"))
                try:
                    liquidation_data, meta = await coinglass.get_liquidation_aggregated(
                        symbol=params.asset,
                        lookback_hours=params.lookback_hours,
                    )
                    source_metas.append(meta)
                except Exception as exc:
                    logger.warning("coinglass_liquidation_fetch_failed", error=str(exc))
                    warnings.append(f"Coinglass liquidation fetch failed: {exc}")

        elapsed = time.time() - start_time
        logger.info(
            "lending_liquidation_risk_execute_complete",
            asset=params.asset,
            elapsed_ms=round(elapsed * 1000, 2),
        )

        return LendingLiquidationRiskOutput(
            asset=params.asset,
            yields=yields_data,
            liquidations=liquidation_data,
            source_meta=source_metas,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )
