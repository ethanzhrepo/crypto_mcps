"""
hyperliquid_market tool implementation.
"""
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog

from src.core.models import (
    HyperliquidMarketData,
    HyperliquidMarketIncludeField,
    HyperliquidMarketInput,
    HyperliquidMarketOutput,
    SourceMeta,
)
from src.data_sources.hyperliquid import HyperliquidClient

logger = structlog.get_logger()

DEFAULT_FUNDING_LOOKBACK = timedelta(days=7)


class HyperliquidMarketTool:
    """Hyperliquid market data tool."""

    def __init__(self, hyperliquid_client: Optional[HyperliquidClient] = None):
        self.hyperliquid = hyperliquid_client or HyperliquidClient()
        logger.info("hyperliquid_market_tool_initialized")

    async def execute(self, params) -> HyperliquidMarketOutput:
        if isinstance(params, dict):
            params = HyperliquidMarketInput(**params)

        start_time = time.time()
        warnings: list[str] = []
        source_metas: list[SourceMeta] = []

        include_fields = {f.value for f in params.include_fields}
        include_all = HyperliquidMarketIncludeField.ALL.value in include_fields

        data = HyperliquidMarketData()
        symbol = params.symbol.upper()

        if include_all or HyperliquidMarketIncludeField.FUNDING.value in include_fields:
            try:
                funding_start = params.start_time
                funding_end = params.end_time
                if funding_start is None:
                    anchor_ms = (
                        funding_end
                        if funding_end is not None
                        else int(datetime.now(timezone.utc).timestamp() * 1000)
                    )
                    funding_start = int(
                        anchor_ms - (DEFAULT_FUNDING_LOOKBACK.total_seconds() * 1000)
                    )

                if (
                    funding_end is not None
                    and funding_start is not None
                    and funding_end < funding_start
                ):
                    warnings.append("Hyperliquid funding skipped: end_time < start_time.")
                else:
                    funding, meta = await self.hyperliquid.get_funding_history(
                        symbol,
                        start_time=funding_start,
                        end_time=funding_end,
                    )
                    data.funding = funding
                    source_metas.append(meta)
            except Exception as exc:
                logger.warning("hyperliquid_funding_failed", error=str(exc))
                warnings.append(f"Hyperliquid funding fetch failed: {exc}")

        if include_all or HyperliquidMarketIncludeField.OPEN_INTEREST.value in include_fields:
            try:
                oi, meta = await self.hyperliquid.get_open_interest(symbol)
                data.open_interest = oi
                source_metas.append(meta)
            except Exception as exc:
                logger.warning("hyperliquid_open_interest_failed", error=str(exc))
                warnings.append(f"Hyperliquid open interest fetch failed: {exc}")

        if include_all or HyperliquidMarketIncludeField.ORDERBOOK.value in include_fields:
            try:
                orderbook, meta = await self.hyperliquid.get_l2_book(symbol)
                data.orderbook = orderbook
                source_metas.append(meta)
            except Exception as exc:
                logger.warning("hyperliquid_orderbook_failed", error=str(exc))
                warnings.append(f"Hyperliquid orderbook fetch failed: {exc}")

        if include_all or HyperliquidMarketIncludeField.TRADES.value in include_fields:
            try:
                trades, meta = await self.hyperliquid.get_recent_trades(symbol)
                data.trades = trades
                source_metas.append(meta)
            except Exception as exc:
                logger.warning("hyperliquid_trades_failed", error=str(exc))
                warnings.append(f"Hyperliquid trades fetch failed: {exc}")

        if include_all or HyperliquidMarketIncludeField.ASSET_CONTEXTS.value in include_fields:
            try:
                asset_ctxs, meta = await self.hyperliquid.get_asset_contexts()
                data.asset_contexts = asset_ctxs
                source_metas.append(meta)
            except Exception as exc:
                logger.warning("hyperliquid_asset_ctxs_failed", error=str(exc))
                warnings.append(f"Hyperliquid asset contexts fetch failed: {exc}")

        elapsed = time.time() - start_time
        logger.info(
            "hyperliquid_market_execute_complete",
            symbol=symbol,
            elapsed_ms=round(elapsed * 1000, 2),
        )

        return HyperliquidMarketOutput(
            symbol=symbol,
            data=data,
            source_meta=source_metas,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )
