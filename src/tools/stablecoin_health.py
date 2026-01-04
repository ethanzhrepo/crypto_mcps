"""
stablecoin_health tool implementation.
"""
import time
from datetime import datetime
from typing import Optional

import structlog

from src.core.models import StablecoinHealthInput, StablecoinHealthOutput, SourceMeta
from src.data_sources.defillama import DefiLlamaClient

logger = structlog.get_logger()


class StablecoinHealthTool:
    """Stablecoin health tool."""

    def __init__(self, defillama_client: Optional[DefiLlamaClient] = None):
        self.defillama = defillama_client or DefiLlamaClient()
        logger.info("stablecoin_health_tool_initialized")

    async def execute(self, params) -> StablecoinHealthOutput:
        if isinstance(params, dict):
            params = StablecoinHealthInput(**params)

        start_time = time.time()
        warnings: list[str] = []
        source_metas: list[SourceMeta] = []

        stablecoins: list[dict] = []
        try:
            data, meta = await self.defillama.get_stablecoins()
            source_metas.append(meta)
            stablecoins = data
        except Exception as exc:
            logger.warning("stablecoins_fetch_failed", error=str(exc))
            warnings.append(f"Stablecoin data fetch failed: {exc}")

        if params.symbol:
            symbol_upper = params.symbol.upper()
            stablecoins = [
                s for s in stablecoins
                if str(s.get("stablecoin", "")).upper() == symbol_upper
            ]

        if params.chains:
            chain_set = {c.lower() for c in params.chains}
            filtered = []
            for coin in stablecoins:
                chains = coin.get("chains", {}) or {}
                if any(chain.lower() in chain_set for chain in chains.keys()):
                    filtered.append(coin)
            stablecoins = filtered

        elapsed = time.time() - start_time
        logger.info(
            "stablecoin_health_execute_complete",
            symbol=params.symbol,
            elapsed_ms=round(elapsed * 1000, 2),
        )

        return StablecoinHealthOutput(
            symbol=params.symbol,
            stablecoins=stablecoins,
            source_meta=source_metas,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )
