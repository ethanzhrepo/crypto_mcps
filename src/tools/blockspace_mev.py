"""
blockspace_mev tool implementation.
"""
import time
from datetime import datetime
from typing import Optional

import structlog

from src.core.models import BlockspaceMevInput, BlockspaceMevOutput, SourceMeta
from src.data_sources.flashbots import FlashbotsMevClient
from src.data_sources.etherscan.client import EtherscanClient
from src.utils.config import config

logger = structlog.get_logger()


class BlockspaceMevTool:
    """Blockspace + MEV-Boost tool."""

    def __init__(
        self,
        flashbots_client: Optional[FlashbotsMevClient] = None,
        etherscan_client: Optional[EtherscanClient] = None,
    ):
        self.flashbots = flashbots_client or FlashbotsMevClient()
        self.etherscan = etherscan_client
        logger.info("blockspace_mev_tool_initialized")

    async def execute(self, params) -> BlockspaceMevOutput:
        if isinstance(params, dict):
            params = BlockspaceMevInput(**params)

        start_time = time.time()
        warnings: list[str] = []
        source_metas: list[SourceMeta] = []
        mev_boost: dict = {}
        gas_oracle: Optional[dict] = None

        try:
            builder_blocks, meta = await self.flashbots.get_builder_blocks_received(limit=params.limit)
            source_metas.append(meta)
            proposer_blocks, meta2 = await self.flashbots.get_proposer_payload_delivered(limit=params.limit)
            source_metas.append(meta2)

            def _sum_value(rows):
                total = 0
                for row in rows or []:
                    value = row.get("value") if isinstance(row, dict) else None
                    if value is None:
                        continue
                    try:
                        total += int(value)
                    except (ValueError, TypeError):
                        continue
                return total

            mev_boost = {
                "builder_blocks_received": builder_blocks,
                "proposer_payload_delivered": proposer_blocks,
                "summary": {
                    "builder_blocks_count": len(builder_blocks) if isinstance(builder_blocks, list) else 0,
                    "proposer_blocks_count": len(proposer_blocks) if isinstance(proposer_blocks, list) else 0,
                    "total_builder_value_wei": _sum_value(builder_blocks),
                    "total_proposer_value_wei": _sum_value(proposer_blocks),
                },
            }
        except Exception as exc:
            logger.warning("flashbots_fetch_failed", error=str(exc))
            warnings.append(f"Flashbots MEV-Boost fetch failed: {exc}")

        if params.chain.lower() != "ethereum":
            warnings.append("Gas oracle currently supports ethereum only.")
        else:
            etherscan = self.etherscan or EtherscanClient(
                chain="ethereum",
                api_key=config.get_api_key("etherscan"),
            )
            try:
                gas_oracle = await etherscan.get_gas_oracle()
            except Exception as exc:
                logger.warning("etherscan_gas_oracle_failed", error=str(exc))
                warnings.append(f"Etherscan gas oracle fetch failed: {exc}")

        elapsed = time.time() - start_time
        logger.info(
            "blockspace_mev_execute_complete",
            chain=params.chain,
            elapsed_ms=round(elapsed * 1000, 2),
        )

        return BlockspaceMevOutput(
            chain=params.chain,
            mev_boost=mev_boost,
            gas_oracle=gas_oracle,
            source_meta=source_metas,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )
