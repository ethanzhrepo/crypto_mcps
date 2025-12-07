"""
onchain_dex_liquidity 工具实现

基于 The Graph 获取 Uniswap v3 流动性信息：
- 单池：指定 pool_address，支持 ticks 分布
- 按代币：指定 token_address，返回该 token 相关池子
- Top 池子：按 TVL 排名前 N 的池子
"""
import time
from datetime import datetime
from typing import Optional

import structlog

from src.core.models import (
    DEXLiquidityData,
    OnchainDEXLiquidityInput,
    OnchainDEXLiquidityOutput,
    SourceMeta,
)
from src.data_sources.thegraph import TheGraphClient

logger = structlog.get_logger()


class OnchainDEXLiquidityTool:
    """onchain_dex_liquidity 工具"""

    def __init__(self, thegraph_client: Optional[TheGraphClient] = None):
        self.thegraph = thegraph_client or TheGraphClient()
        logger.info("onchain_dex_liquidity_tool_initialized")

    async def execute(
        self, params: OnchainDEXLiquidityInput
    ) -> OnchainDEXLiquidityOutput:
        start_time = time.time()
        logger.info(
            "onchain_dex_liquidity_execute_start",
            chain=params.chain,
            token_address=params.token_address,
            pool_address=params.pool_address,
            include_ticks=params.include_ticks,
        )

        warnings: list[str] = []
        source_metas: list[SourceMeta] = []

        protocol = "uniswap_v3"
        chain = params.chain

        # 1) 优先单池
        if params.pool_address:
            pool_data, meta = await self.thegraph.get_uniswap_v3_pool(
                pool_address=params.pool_address,
                chain=chain,
            )
            pools = [pool_data] if pool_data else []
            total_tvl = pool_data.get("tvl_usd", 0) if pool_data else 0

            ticks = None
            if params.include_ticks and params.pool_address:
                ticks_data, _ = await self.thegraph.get_uniswap_v3_pool_ticks(
                    pool_address=params.pool_address,
                    chain=chain,
                    first=500,
                )
                ticks = ticks_data

            dex_liquidity = DEXLiquidityData(
                protocol=protocol,
                chain=chain,
                pool_address=params.pool_address,
                total_liquidity_usd=total_tvl,
                pools=pools,
                ticks=ticks,
                timestamp=datetime.utcnow().isoformat() + "Z",
            )
            source_metas.append(meta)

        # 2) 按代币查询相关池子
        elif params.token_address:
            pools_data, meta = await self.thegraph.get_uniswap_v3_pools_by_token(
                token_address=params.token_address,
                chain=chain,
                limit=10,
            )
            total_tvl = sum(p.get("tvl_usd", 0) for p in pools_data)

            dex_liquidity = DEXLiquidityData(
                protocol=protocol,
                chain=chain,
                token=params.token_address,
                total_liquidity_usd=total_tvl,
                pools=pools_data,
                ticks=None,
                timestamp=datetime.utcnow().isoformat() + "Z",
            )
            source_metas.append(meta)

        # 3) Top 池子
        else:
            pools_data, meta = await self.thegraph.get_uniswap_v3_top_pools(
                chain=chain,
                limit=20,
            )
            total_tvl = sum(p.get("tvl_usd", 0) for p in pools_data)

            dex_liquidity = DEXLiquidityData(
                protocol=protocol,
                chain=chain,
                total_liquidity_usd=total_tvl,
                pools=pools_data,
                ticks=None,
                timestamp=datetime.utcnow().isoformat() + "Z",
            )
            source_metas.append(meta)

        elapsed = time.time() - start_time
        logger.info(
            "onchain_dex_liquidity_execute_complete",
            chain=chain,
            elapsed_ms=round(elapsed * 1000, 2),
        )

        return OnchainDEXLiquidityOutput(
            dex_liquidity=dex_liquidity,
            source_meta=source_metas,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )

