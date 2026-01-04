"""
options_vol_skew tool implementation.
"""
import time
from datetime import datetime
from typing import Optional

import structlog

from src.core.models import OptionsVolSkewInput, OptionsVolSkewOutput, SourceMeta
from src.data_sources.binance import BinanceOptionsClient
from src.data_sources.deribit import DeribitClient
from src.data_sources.okx import OKXClient

logger = structlog.get_logger()


class OptionsVolSkewTool:
    """Options volatility/skew tool."""

    def __init__(
        self,
        deribit_client: Optional[DeribitClient] = None,
        okx_client: Optional[OKXClient] = None,
        binance_options_client: Optional[BinanceOptionsClient] = None,
    ):
        self.deribit = deribit_client or DeribitClient()
        self.okx = okx_client or OKXClient()
        self.binance = binance_options_client or BinanceOptionsClient()
        logger.info("options_vol_skew_tool_initialized")

    async def execute(self, params) -> OptionsVolSkewOutput:
        if isinstance(params, dict):
            params = OptionsVolSkewInput(**params)

        start_time = time.time()
        warnings: list[str] = []
        source_metas: list[SourceMeta] = []
        data: dict = {}

        providers = {p.lower() for p in params.providers}

        if "deribit" in providers:
            try:
                vol_index, meta = await self.deribit.get_volatility_index(currency=params.symbol)
                source_metas.append(meta)
                data["deribit"] = {"volatility_index": vol_index}

                if params.expiry:
                    instruments, meta2 = await self.deribit.get_instruments(currency=params.symbol)
                    source_metas.append(meta2)
                    expiry = params.expiry.upper()
                    filtered = [i for i in instruments if expiry in str(i.get("instrument_name", ""))]
                    data["deribit"]["instruments"] = filtered
            except Exception as exc:
                logger.warning("deribit_options_fetch_failed", error=str(exc))
                warnings.append(f"Deribit options fetch failed: {exc}")

        if "okx" in providers:
            try:
                underlying = f"{params.symbol.upper()}-USD"
                inst_id = params.expiry
                okx_summary, meta = await self.okx.get_option_summary(
                    inst_id=inst_id,
                    underlying=underlying,
                )
                source_metas.append(meta)
                data["okx"] = okx_summary
            except Exception as exc:
                logger.warning("okx_options_fetch_failed", error=str(exc))
                warnings.append(f"OKX options fetch failed: {exc}")

        if "binance" in providers:
            try:
                if params.expiry:
                    mark_data, meta = await self.binance.get_mark_data(symbol=params.expiry)
                    source_metas.append(meta)
                    data["binance"] = mark_data
                else:
                    warnings.append("Binance options requires a specific option symbol in expiry field.")
            except Exception as exc:
                logger.warning("binance_options_fetch_failed", error=str(exc))
                warnings.append(f"Binance options fetch failed: {exc}")

        elapsed = time.time() - start_time
        logger.info(
            "options_vol_skew_execute_complete",
            symbol=params.symbol,
            elapsed_ms=round(elapsed * 1000, 2),
        )

        return OptionsVolSkewOutput(
            symbol=params.symbol,
            data=data,
            source_meta=source_metas,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )
