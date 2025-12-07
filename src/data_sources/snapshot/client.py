"""
Snapshot GraphQL API客户端 - 链下治理数据

API文档: https://docs.snapshot.org/graphql-api
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from src.core.models import GovernanceData, GovernanceProposal, SourceMeta
from src.core.source_meta import SourceMetaBuilder
from src.utils.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SnapshotClient:
    """Snapshot GraphQL API客户端"""

    GRAPHQL_URL = "https://hub.snapshot.org/graphql"

    def __init__(self):
        """初始化Snapshot客户端（无需API key）"""
        self.name = "snapshot"
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """获取HTTP客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=15.0,
                headers={"Content-Type": "application/json"},
            )
        return self._client

    @client.setter
    def client(self, value: httpx.AsyncClient):
        """允许在测试中注入自定义HTTP客户端"""
        self._client = value

    @client.deleter
    def client(self):
        """属性删除时清空客户端引用"""
        self._client = None

    async def close(self):
        """关闭HTTP客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_proposals(
        self,
        space: str,
        state: Optional[str] = None,
        limit: int = 20,
    ) -> tuple[GovernanceData, SourceMeta]:
        """
        获取治理提案

        Args:
            space: Snapshot空间ID，如 "uniswap.eth", "aave.eth"
            state: 提案状态过滤 (active, closed, pending)
            limit: 返回数量限制

        Returns:
            (治理数据, SourceMeta)
        """
        # 构建GraphQL查询
        where_clause = f'space: "{space}"'
        if state:
            where_clause += f', state: "{state}"'

        query = f"""
        query {{
            proposals(
                first: {limit},
                skip: 0,
                where: {{ {where_clause} }},
                orderBy: "created",
                orderDirection: desc
            ) {{
                id
                title
                state
                start
                end
                choices
                scores
                author
            }}
            space(id: "{space}") {{
                id
                name
                proposalsCount
            }}
        }}
        """

        start_time = datetime.utcnow()

        try:
            response = await self.client.post(
                self.GRAPHQL_URL,
                json={"query": query},
            )
            response.raise_for_status()
            data = response.json()

            # 解析响应
            proposals_data = data.get("data", {}).get("proposals", [])
            space_data = data.get("data", {}).get("space") or {}

            # 转换为GovernanceProposal模型
            proposals = []
            active_count = 0
            for p in proposals_data:
                proposal = GovernanceProposal(
                    id=p.get("id", ""),
                    title=p.get("title", ""),
                    state=p.get("state", "unknown"),
                    start_time=datetime.fromtimestamp(p.get("start", 0)).isoformat() + "Z",
                    end_time=datetime.fromtimestamp(p.get("end", 0)).isoformat() + "Z",
                    choices=p.get("choices", []),
                    scores=p.get("scores"),
                    author=p.get("author", ""),
                )
                proposals.append(proposal)
                if p.get("state") == "active":
                    active_count += 1

            governance_data = GovernanceData(
                dao=space_data.get("name", space),
                total_proposals=space_data.get("proposalsCount", len(proposals)),
                active_proposals=active_count,
                recent_proposals=proposals,
                timestamp=datetime.utcnow().isoformat() + "Z",
            )

            # 构建SourceMeta
            response_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            source_meta = SourceMetaBuilder.build(
                provider=self.name,
                endpoint=f"/graphql?space={space}",
                ttl_seconds=300,
                response_time_ms=response_time_ms,
            )

            return governance_data, source_meta

        except Exception as e:
            logger.error(f"Snapshot API error: {e}", space=space)
            raise

    async def get_space_info(self, space: str) -> tuple[Dict, SourceMeta]:
        """
        获取空间信息

        Args:
            space: Snapshot空间ID

        Returns:
            (空间信息, SourceMeta)
        """
        query = f"""
        query {{
            space(id: "{space}") {{
                id
                name
                about
                network
                symbol
                members
                proposalsCount
                votesCount
                followersCount
            }}
        }}
        """

        start_time = datetime.utcnow()

        response = await self.client.post(
            self.GRAPHQL_URL,
            json={"query": query},
        )
        response.raise_for_status()
        data = response.json()

        space_data = data.get("data", {}).get("space") or {}

        response_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        source_meta = SourceMetaBuilder.build(
            provider=self.name,
            endpoint=f"/graphql?space={space}",
            ttl_seconds=600,
            response_time_ms=response_time_ms,
        )

        return space_data, source_meta

    async def get_voting_power(
        self,
        space: str,
        voter: str,
        proposal: Optional[str] = None
    ) -> tuple[Dict, SourceMeta]:
        """
        获取用户投票权重

        Args:
            space: Snapshot空间ID，如 "uniswap.eth"
            voter: 用户钱包地址
            proposal: 提案ID（可选，如果不提供则需要获取最新提案）

        Returns:
            (投票权重数据, SourceMeta)
        """
        start_time = datetime.utcnow()

        # 如果没有提供 proposal，先获取一个最新的提案
        if not proposal:
            proposals_query = f"""
            query {{
                proposals(
                    first: 1,
                    where: {{ space: "{space}" }},
                    orderBy: "created",
                    orderDirection: desc
                ) {{
                    id
                }}
            }}
            """
            response = await self.client.post(
                self.GRAPHQL_URL,
                json={"query": proposals_query},
            )
            response.raise_for_status()
            data = response.json()
            proposals = data.get("data", {}).get("proposals", [])
            if proposals:
                proposal = proposals[0].get("id")
            else:
                # 没有提案，返回空数据
                response_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                source_meta = SourceMetaBuilder.build(
                    provider=self.name,
                    endpoint=f"/graphql?vp={space}",
                    ttl_seconds=300,
                    response_time_ms=response_time_ms,
                )
                return {
                    "vp": 0,
                    "vp_by_strategy": [],
                    "vp_state": "no_proposal",
                    "space": space,
                    "voter": voter,
                }, source_meta

        # 查询投票权重
        query = f"""
        query {{
            vp(
                voter: "{voter}",
                space: "{space}",
                proposal: "{proposal}"
            ) {{
                vp
                vp_by_strategy
                vp_state
            }}
        }}
        """

        response = await self.client.post(
            self.GRAPHQL_URL,
            json={"query": query},
        )
        response.raise_for_status()
        data = response.json()

        vp_data = data.get("data", {}).get("vp") or {}

        response_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        source_meta = SourceMetaBuilder.build(
            provider=self.name,
            endpoint=f"/graphql?vp={space}",
            ttl_seconds=300,
            response_time_ms=response_time_ms,
        )

        return {
            "vp": vp_data.get("vp", 0),
            "vp_by_strategy": vp_data.get("vp_by_strategy", []),
            "vp_state": vp_data.get("vp_state", "unknown"),
            "space": space,
            "voter": voter,
            "proposal": proposal,
        }, source_meta

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            query = '{ spaces(first: 1) { id } }'
            response = await self.client.post(
                self.GRAPHQL_URL,
                json={"query": query},
            )
            return response.status_code == 200
        except Exception:
            return False
