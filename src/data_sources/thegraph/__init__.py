"""
The Graph API客户端

提供DeFi协议链上数据：
- Uniswap v3 流动性池
- Tick分布
- 交易量统计
- 费用收入
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from src.core.models import SourceMeta
from src.data_sources.base import BaseDataSource


class TheGraphClient(BaseDataSource):
    """The Graph子图查询客户端"""

    # 公共子图端点
    SUBGRAPH_ENDPOINTS = {
        "uniswap_v3_ethereum": "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3",
        "uniswap_v3_arbitrum": "https://api.thegraph.com/subgraphs/name/ianlapham/uniswap-arbitrum-one",
        "uniswap_v3_optimism": "https://api.thegraph.com/subgraphs/name/ianlapham/optimism-post-regenesis",
        "uniswap_v3_polygon": "https://api.thegraph.com/subgraphs/name/ianlapham/uniswap-v3-polygon",
        "uniswap_v2": "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2",
        "aave_v3": "https://api.thegraph.com/subgraphs/name/aave/protocol-v3",
        "compound_v2": "https://api.thegraph.com/subgraphs/name/graphprotocol/compound-v2",
        "curve": "https://api.thegraph.com/subgraphs/name/messari/curve-finance-ethereum",
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化The Graph客户端

        Args:
            api_key: The Graph API密钥（可选，使用免费公共端点则不需要）
        """
        super().__init__(
            name="thegraph",
            base_url="https://api.thegraph.com",
            timeout=15.0,
            requires_api_key=False,
        )
        self.api_key = api_key

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def fetch_raw(self, endpoint: str, params: Optional[Dict] = None, base_url_override: Optional[str] = None, headers: Optional[Dict[str, str]] = None) -> Any:
        """获取原始数据（实现基类抽象方法）"""
        return await self._make_request("POST", endpoint, params, base_url_override, headers)

    def transform(self, raw_data: Any, data_type: str) -> Any:
        """转换原始数据（基类要求）"""
        if data_type == "uniswap_pool":
            return self._transform_uniswap_pool(raw_data)
        elif data_type == "uniswap_tick":
            return self._transform_tick(raw_data)
        else:
            return raw_data

    async def query_subgraph(
        self, subgraph_url: str, query: str, variables: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        执行GraphQL查询

        Args:
            subgraph_url: 子图URL
            query: GraphQL查询字符串
            variables: 查询变量

        Returns:
            查询结果
        """
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                subgraph_url,
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            result = response.json()

            if "errors" in result:
                raise Exception(f"GraphQL error: {result['errors']}")

            return result.get("data", {})

    # ==================== Uniswap v3 专用查询 ====================

    async def get_uniswap_v3_pool(
        self, pool_address: str, chain: str = "ethereum"
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取Uniswap v3池子信息

        Args:
            pool_address: 池子地址
            chain: 链名称

        Returns:
            (池子数据, SourceMeta)
        """
        subgraph = self.SUBGRAPH_ENDPOINTS.get(
            f"uniswap_v3_{chain}", self.SUBGRAPH_ENDPOINTS["uniswap_v3_ethereum"]
        )

        query = """
        query GetPool($poolId: ID!) {
          pool(id: $poolId) {
            id
            token0 {
              id
              symbol
              name
              decimals
            }
            token1 {
              id
              symbol
              name
              decimals
            }
            feeTier
            liquidity
            sqrtPrice
            tick
            token0Price
            token1Price
            volumeUSD
            volumeToken0
            volumeToken1
            txCount
            totalValueLockedToken0
            totalValueLockedToken1
            totalValueLockedUSD
            feesUSD
          }
        }
        """

        variables = {"poolId": pool_address.lower()}

        data = await self.query_subgraph(subgraph, query, variables)

        meta = SourceMeta(
            provider="thegraph",
            endpoint=subgraph,
            fetched_at=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=300,  # 5分钟缓存
            cache_hit=False,
        )

        return self._transform_uniswap_pool(data.get("pool", {})), meta

    async def get_uniswap_v3_pool_ticks(
        self,
        pool_address: str,
        skip: int = 0,
        first: int = 100,
        chain: str = "ethereum",
    ) -> tuple[List[Dict], SourceMeta]:
        """
        获取Uniswap v3池子的tick分布（流动性分布）

        Args:
            pool_address: 池子地址
            skip: 跳过前N个
            first: 返回数量
            chain: 链名称

        Returns:
            (tick列表, SourceMeta)
        """
        subgraph = self.SUBGRAPH_ENDPOINTS.get(
            f"uniswap_v3_{chain}", self.SUBGRAPH_ENDPOINTS["uniswap_v3_ethereum"]
        )

        query = """
        query GetPoolTicks($poolAddress: String!, $skip: Int!, $first: Int!) {
          ticks(
            where: { poolAddress: $poolAddress }
            skip: $skip
            first: $first
            orderBy: tickIdx
            orderDirection: asc
          ) {
            tickIdx
            liquidityGross
            liquidityNet
            price0
            price1
            volumeToken0
            volumeToken1
            volumeUSD
            feesUSD
          }
        }
        """

        variables = {
            "poolAddress": pool_address.lower(),
            "skip": skip,
            "first": first,
        }

        data = await self.query_subgraph(subgraph, query, variables)

        meta = SourceMeta(
            provider="thegraph",
            endpoint=subgraph,
            fetched_at=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=300,
            cache_hit=False,
        )

        ticks = data.get("ticks", [])
        return [self._transform_tick(t) for t in ticks], meta

    async def get_uniswap_v3_pools_by_token(
        self, token_address: str, limit: int = 10, chain: str = "ethereum"
    ) -> tuple[List[Dict], SourceMeta]:
        """
        按代币查询相关池子

        Args:
            token_address: 代币地址
            limit: 返回数量
            chain: 链名称

        Returns:
            (池子列表, SourceMeta)
        """
        subgraph = self.SUBGRAPH_ENDPOINTS.get(
            f"uniswap_v3_{chain}", self.SUBGRAPH_ENDPOINTS["uniswap_v3_ethereum"]
        )

        query = """
        query GetPoolsByToken($token: String!, $first: Int!) {
          pools(
            where: {
              or: [
                { token0: $token }
                { token1: $token }
              ]
            }
            first: $first
            orderBy: totalValueLockedUSD
            orderDirection: desc
          ) {
            id
            token0 {
              id
              symbol
              name
            }
            token1 {
              id
              symbol
              name
            }
            feeTier
            liquidity
            totalValueLockedUSD
            volumeUSD
            txCount
          }
        }
        """

        variables = {"token": token_address.lower(), "first": limit}

        data = await self.query_subgraph(subgraph, query, variables)

        meta = SourceMeta(
            provider="thegraph",
            endpoint=subgraph,
            fetched_at=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=600,
            cache_hit=False,
        )

        pools = data.get("pools", [])
        return [self._transform_uniswap_pool(p) for p in pools], meta

    async def get_uniswap_v3_top_pools(
        self, limit: int = 20, chain: str = "ethereum"
    ) -> tuple[List[Dict], SourceMeta]:
        """
        获取TVL最高的池子

        Args:
            limit: 返回数量
            chain: 链名称

        Returns:
            (池子列表, SourceMeta)
        """
        subgraph = self.SUBGRAPH_ENDPOINTS.get(
            f"uniswap_v3_{chain}", self.SUBGRAPH_ENDPOINTS["uniswap_v3_ethereum"]
        )

        query = """
        query GetTopPools($first: Int!) {
          pools(
            first: $first
            orderBy: totalValueLockedUSD
            orderDirection: desc
          ) {
            id
            token0 {
              id
              symbol
              name
            }
            token1 {
              id
              symbol
              name
            }
            feeTier
            liquidity
            totalValueLockedUSD
            volumeUSD
            feesUSD
            txCount
            token0Price
            token1Price
          }
        }
        """

        variables = {"first": limit}

        data = await self.query_subgraph(subgraph, query, variables)

        meta = SourceMeta(
            provider="thegraph",
            endpoint=subgraph,
            fetched_at=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=600,
            cache_hit=False,
        )

        pools = data.get("pools", [])
        return [self._transform_uniswap_pool(p) for p in pools], meta

    # ==================== 数据转换 ====================

    def _transform_uniswap_pool(self, pool: Dict) -> Dict:
        """转换Uniswap池子数据"""
        if not pool:
            return {}

        token0 = pool.get("token0", {})
        token1 = pool.get("token1", {})

        return {
            "pool_address": pool.get("id"),
            "token0": {
                "address": token0.get("id"),
                "symbol": token0.get("symbol"),
                "name": token0.get("name"),
                "decimals": int(token0.get("decimals", 18)),
            },
            "token1": {
                "address": token1.get("id"),
                "symbol": token1.get("symbol"),
                "name": token1.get("name"),
                "decimals": int(token1.get("decimals", 18)),
            },
            "fee_tier": int(pool.get("feeTier", 0)),
            "liquidity": float(pool.get("liquidity", 0)),
            "sqrt_price": float(pool.get("sqrtPrice", 0)) if pool.get("sqrtPrice") else None,
            "tick": int(pool.get("tick", 0)) if pool.get("tick") else None,
            "token0_price": float(pool.get("token0Price", 0)) if pool.get("token0Price") else None,
            "token1_price": float(pool.get("token1Price", 0)) if pool.get("token1Price") else None,
            "tvl_usd": float(pool.get("totalValueLockedUSD", 0)),
            "tvl_token0": float(pool.get("totalValueLockedToken0", 0)) if pool.get("totalValueLockedToken0") else None,
            "tvl_token1": float(pool.get("totalValueLockedToken1", 0)) if pool.get("totalValueLockedToken1") else None,
            "volume_usd": float(pool.get("volumeUSD", 0)),
            "volume_token0": float(pool.get("volumeToken0", 0)) if pool.get("volumeToken0") else None,
            "volume_token1": float(pool.get("volumeToken1", 0)) if pool.get("volumeToken1") else None,
            "fees_usd": float(pool.get("feesUSD", 0)) if pool.get("feesUSD") else None,
            "tx_count": int(pool.get("txCount", 0)),
        }

    def _transform_tick(self, tick: Dict) -> Dict:
        """转换tick数据"""
        return {
            "tick_idx": int(tick.get("tickIdx", 0)),
            "liquidity_gross": float(tick.get("liquidityGross", 0)),
            "liquidity_net": float(tick.get("liquidityNet", 0)),
            "price0": float(tick.get("price0", 0)) if tick.get("price0") else None,
            "price1": float(tick.get("price1", 0)) if tick.get("price1") else None,
            "volume_usd": float(tick.get("volumeUSD", 0)) if tick.get("volumeUSD") else None,
            "fees_usd": float(tick.get("feesUSD", 0)) if tick.get("feesUSD") else None,
        }
