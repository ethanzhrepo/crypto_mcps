"""
Tally GraphQL API客户端 - 链上治理数据

API文档: https://docs.tally.xyz/
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from src.core.models import GovernanceData, GovernanceProposal, SourceMeta
from src.core.source_meta import SourceMetaBuilder
from src.utils.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TallyClient:
    """Tally GraphQL API客户端"""

    GRAPHQL_URL = "https://api.tally.xyz/query"

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化Tally客户端

        Args:
            api_key: API密钥（可选，从配置获取）
        """
        self.name = "tally"
        self.api_key = api_key or config.get_api_key("tally")
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """获取HTTP客户端"""
        if self._client is None:
            headers = {
                "Content-Type": "application/json",
            }
            if self.api_key:
                headers["Api-Key"] = self.api_key
            self._client = httpx.AsyncClient(
                timeout=15.0,
                headers=headers,
            )
        return self._client

    async def close(self):
        """关闭HTTP客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_proposals(
        self,
        governor_address: str,
        chain_id: str = "eip155:1",
        limit: int = 20,
    ) -> tuple[GovernanceData, SourceMeta]:
        """
        获取链上治理提案

        Args:
            governor_address: Governor合约地址
            chain_id: 链ID (格式: eip155:1)
            limit: 返回数量限制

        Returns:
            (治理数据, SourceMeta)
        """
        query = """
        query Proposals($governorId: AccountID!, $first: Int!) {
            proposals(
                first: $first
                where: { governorId: $governorId }
                orderBy: { field: CREATED_AT, direction: DESC }
            ) {
                nodes {
                    id
                    title
                    description
                    eta
                    createdAt
                    start {
                        timestamp
                    }
                    end {
                        timestamp
                    }
                    status
                    governor {
                        name
                    }
                    proposer {
                        address
                    }
                    voteStats {
                        votes
                        weight
                        support
                    }
                }
            }
            governor(id: $governorId) {
                name
                proposalCount
            }
        }
        """

        governor_id = f"{chain_id}:{governor_address}"

        variables = {
            "governorId": governor_id,
            "first": limit,
        }

        start_time = datetime.utcnow()

        try:
            response = await self.client.post(
                self.GRAPHQL_URL,
                json={"query": query, "variables": variables},
            )
            response.raise_for_status()
            data = response.json()

            # 检查错误
            if "errors" in data:
                logger.error(f"Tally API errors: {data['errors']}")
                raise Exception(f"Tally API error: {data['errors']}")

            # 解析响应
            proposals_data = data.get("data", {}).get("proposals", {}).get("nodes", [])
            governor_data = data.get("data", {}).get("governor", {})

            # 转换为GovernanceProposal模型
            proposals = []
            active_count = 0
            for p in proposals_data:
                state = self._map_tally_status(p.get("status", ""))

                # 解析投票数据
                vote_stats = p.get("voteStats", [])
                choices = []
                scores = []
                for vs in vote_stats:
                    support = vs.get("support", "")
                    choices.append(support)
                    scores.append(float(vs.get("weight", 0)))

                proposal = GovernanceProposal(
                    id=p.get("id", ""),
                    title=p.get("title", "") or p.get("description", "")[:100],
                    state=state,
                    start_time=p.get("start", {}).get("timestamp", ""),
                    end_time=p.get("end", {}).get("timestamp", ""),
                    choices=choices if choices else ["For", "Against", "Abstain"],
                    scores=scores if scores else None,
                    author=p.get("proposer", {}).get("address", ""),
                )
                proposals.append(proposal)
                if state == "active":
                    active_count += 1

            governance_data = GovernanceData(
                dao=governor_data.get("name", "Unknown"),
                total_proposals=governor_data.get("proposalCount", len(proposals)),
                active_proposals=active_count,
                recent_proposals=proposals,
                timestamp=datetime.utcnow().isoformat() + "Z",
            )

            # 构建SourceMeta
            response_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            source_meta = SourceMetaBuilder.build(
                provider=self.name,
                endpoint=f"/query?governor={governor_address}",
                ttl_seconds=300,
                response_time_ms=response_time_ms,
            )

            return governance_data, source_meta

        except Exception as e:
            logger.error(f"Tally API error: {e}", governor=governor_address)
            raise

    def _map_tally_status(self, status: str) -> str:
        """映射Tally状态到标准状态"""
        status_map = {
            "PENDING": "pending",
            "ACTIVE": "active",
            "CANCELED": "closed",
            "DEFEATED": "closed",
            "SUCCEEDED": "closed",
            "QUEUED": "closed",
            "EXPIRED": "closed",
            "EXECUTED": "closed",
        }
        return status_map.get(status.upper(), "unknown")

    async def get_governor_info(
        self,
        governor_address: str,
        chain_id: str = "eip155:1",
    ) -> tuple[Dict, SourceMeta]:
        """
        获取Governor合约信息

        Args:
            governor_address: Governor合约地址
            chain_id: 链ID

        Returns:
            (Governor信息, SourceMeta)
        """
        query = """
        query Governor($governorId: AccountID!) {
            governor(id: $governorId) {
                id
                name
                type
                proposalCount
                votersCount
                tokenOwnersCount
                delegatesCount
            }
        }
        """

        governor_id = f"{chain_id}:{governor_address}"

        start_time = datetime.utcnow()

        response = await self.client.post(
            self.GRAPHQL_URL,
            json={"query": query, "variables": {"governorId": governor_id}},
        )
        response.raise_for_status()
        data = response.json()

        governor_data = data.get("data", {}).get("governor", {})

        response_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        source_meta = SourceMetaBuilder.build(
            provider=self.name,
            endpoint=f"/query?governor={governor_address}",
            ttl_seconds=600,
            response_time_ms=response_time_ms,
        )

        return governor_data, source_meta

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            query = '{ chains { id } }'
            response = await self.client.post(
                self.GRAPHQL_URL,
                json={"query": query},
            )
            return response.status_code == 200
        except Exception:
            return False
