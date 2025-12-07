"""
onchain_governance 工具实现

聚合 Snapshot（链下）与 Tally（链上）治理数据：
- 当提供 governor_address 时优先使用 Tally；
- 否则如果提供 snapshot_space 则使用 Snapshot；
- 都没有时返回空 GovernanceData。
"""
import time
from datetime import datetime
from typing import Optional

import structlog

from src.core.models import (
    GovernanceData,
    OnchainGovernanceInput,
    OnchainGovernanceOutput,
    SourceMeta,
)
from src.core.source_meta import SourceMetaBuilder
from src.data_sources.snapshot import SnapshotClient
from src.data_sources.tally import TallyClient

logger = structlog.get_logger()


class OnchainGovernanceTool:
    """onchain_governance 工具"""

    def __init__(
        self,
        snapshot_client: Optional[SnapshotClient] = None,
        tally_client: Optional[TallyClient] = None,
    ):
        self.snapshot = snapshot_client or SnapshotClient()
        self.tally = tally_client or TallyClient()
        logger.info("onchain_governance_tool_initialized")

    async def execute(
        self, params: OnchainGovernanceInput
    ) -> OnchainGovernanceOutput:
        start_time = time.time()
        logger.info(
            "onchain_governance_execute_start",
            chain=params.chain,
            snapshot_space=params.snapshot_space,
            governor_address=params.governor_address,
        )

        warnings: list[str] = []
        source_metas: list[SourceMeta] = []

        governance: Optional[GovernanceData] = None

        # 优先 Tally（链上治理）
        if params.governor_address:
            chain_id_map = {
                "ethereum": "eip155:1",
                "polygon": "eip155:137",
                "arbitrum": "eip155:42161",
                "optimism": "eip155:10",
            }
            chain_id = chain_id_map.get(params.chain.lower(), "eip155:1")
            try:
                governance, meta = await self.tally.get_proposals(
                    governor_address=params.governor_address,
                    chain_id=chain_id,
                    limit=20,
                )
                source_metas.append(meta)
            except Exception as exc:
                logger.warning("Failed to fetch governance from Tally", error=str(exc))
                warnings.append(f"Tally governance fetch failed: {exc}")

        # 退回 Snapshot（链下治理）
        if governance is None and params.snapshot_space:
            try:
                governance, meta = await self.snapshot.get_proposals(
                    space=params.snapshot_space,
                    state="all",
                    limit=20,
                )
                source_metas.append(meta)
            except Exception as exc:
                logger.warning("Failed to fetch governance from Snapshot", error=str(exc))
                warnings.append(f"Snapshot governance fetch failed: {exc}")

        # 如果都不可用，返回空治理数据
        if governance is None:
            governance = GovernanceData(
                dao="unknown",
                total_proposals=0,
                active_proposals=0,
                recent_proposals=[],
                timestamp=datetime.utcnow().isoformat() + "Z",
            )
            meta = SourceMetaBuilder.build(
                provider="none",
                endpoint="/onchain_governance",
                ttl_seconds=300,
                response_time_ms=0,
            )
            source_metas.append(meta)

        elapsed = time.time() - start_time
        logger.info(
            "onchain_governance_execute_complete",
            chain=params.chain,
            elapsed_ms=round(elapsed * 1000, 2),
            warnings=len(warnings),
        )

        return OnchainGovernanceOutput(
            governance=governance,
            source_meta=source_metas,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )

