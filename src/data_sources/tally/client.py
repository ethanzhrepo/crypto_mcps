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
        # 新版 Tally API 使用 input 参数
        # 注意：从 proposal.governor 嵌套获取 proposalStats，避免需要额外的 governorId 变量
        # start/end 是 BlockOrTimestamp union 类型，需要 inline fragment
        query = """
        query Proposals($input: ProposalsInput!) {
            proposals(input: $input) {
                nodes {
                    ... on Proposal {
                        id
                        onchainId
                        metadata {
                            title
                            description
                        }
                        start {
                            ... on Block {
                                timestamp
                            }
                            ... on BlocklessTimestamp {
                                timestamp
                            }
                        }
                        end {
                            ... on Block {
                                timestamp
                            }
                            ... on BlocklessTimestamp {
                                timestamp
                            }
                        }
                        status
                        governor {
                            name
                            proposalStats {
                                total
                                active
                            }
                        }
                        proposer {
                            address
                        }
                        voteStats {
                            type
                            votesCount
                            votersCount
                            percent
                        }
                    }
                }
                pageInfo {
                    count
                }
            }
        }
        """

        governor_id = f"{chain_id}:{governor_address}"

        variables = {
            "input": {
                "filters": {
                    "governorId": governor_id,
                },
                "page": {
                    "limit": limit,
                },
                "sort": {
                    "isDescending": True,
                    "sortBy": "id",
                },
            },
        }

        start_time = datetime.utcnow()

        try:
            payload = {"query": query, "variables": variables}
            logger.info(f"Tally API request - governor: {governor_address}, variables: {variables}")
            
            response = await self.client.post(
                self.GRAPHQL_URL,
                json=payload,
            )
            
            # 调试: 打印响应状态和内容
            if response.status_code != 200:
                logger.error(f"Tally API response status: {response.status_code}, body: {response.text[:500]}")
            
            response.raise_for_status()
            data = response.json()

            # 检查错误
            if "errors" in data:
                logger.error(f"Tally API errors: {data['errors']}")
                raise Exception(f"Tally API error: {data['errors']}")

            # 解析响应 - 新版 API 结构
            # 从 proposals[0].governor 获取 governor 信息
            proposals_data = data.get("data", {}).get("proposals", {}).get("nodes", [])
            page_info = data.get("data", {}).get("proposals", {}).get("pageInfo", {})
            
            # 从第一个 proposal 获取 governor 信息
            first_proposal_governor = proposals_data[0].get("governor", {}) if proposals_data else {}

            # 转换为GovernanceProposal模型
            proposals = []
            active_count = 0
            for p in proposals_data:
                state = self._map_tally_status(p.get("status", ""))

                # 解析投票数据 - 新版 API 使用 type, votesCount, percent
                vote_stats = p.get("voteStats", [])
                choices = []
                scores = []
                for vs in vote_stats:
                    vote_type = vs.get("type", "")
                    choices.append(vote_type)
                    scores.append(float(vs.get("percent", 0)))

                # 新版 API 使用 metadata 包裹 title/description
                metadata = p.get("metadata", {}) or {}
                title = metadata.get("title", "") or metadata.get("description", "")[:100] if metadata.get("description") else ""
                
                proposal = GovernanceProposal(
                    id=str(p.get("id", "")),
                    title=title,
                    state=state,
                    start_time=p.get("start", {}).get("timestamp", "") if p.get("start") else "",
                    end_time=p.get("end", {}).get("timestamp", "") if p.get("end") else "",
                    choices=choices if choices else ["For", "Against", "Abstain"],
                    scores=scores if scores else None,
                    author=p.get("proposer", {}).get("address", "") if p.get("proposer") else "",
                )
                proposals.append(proposal)
                if state == "active":
                    active_count += 1

            # 从第一个 proposal 的 governor 获取 proposalStats
            proposal_stats = first_proposal_governor.get("proposalStats", {}) or {}
            governance_data = GovernanceData(
                dao=first_proposal_governor.get("name", "Unknown"),
                total_proposals=proposal_stats.get("total", len(proposals)),
                active_proposals=proposal_stats.get("active", active_count),
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
        # 新版 API 使用 input 参数
        query = """
        query Governor($input: GovernorInput!) {
            governor(input: $input) {
                id
                name
                kind
                proposalStats {
                    total
                    active
                    passed
                    failed
                }
            }
        }
        """

        governor_id = f"{chain_id}:{governor_address}"

        start_time = datetime.utcnow()

        try:
            response = await self.client.post(
                self.GRAPHQL_URL,
                json={"query": query, "variables": {"input": {"id": governor_id}}},
            )
            response.raise_for_status()
            data = response.json()

            if "errors" in data:
                logger.error(f"Tally API errors: {data['errors']}")
                raise Exception(f"Tally API error: {data['errors']}")

            governor_data = data.get("data", {}).get("governor", {})

            response_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            source_meta = SourceMetaBuilder.build(
                provider=self.name,
                endpoint=f"/query?governor={governor_address}",
                ttl_seconds=600,
                response_time_ms=response_time_ms,
            )

            return governor_data, source_meta
        except Exception as e:
            logger.error(f"Tally API error: {e}", governor=governor_address)
            raise

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
