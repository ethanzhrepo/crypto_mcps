"""
GitHub API客户端
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from src.data_sources.base import BaseDataSource
from src.utils.logger import get_logger

logger = get_logger(__name__)


class GitHubClient(BaseDataSource):
    """GitHub API客户端"""

    def __init__(self, token: Optional[str] = None):
        base_url = "https://api.github.com"
        super().__init__(
            name="github",
            base_url=base_url,
            timeout=15.0,
            requires_api_key=False,  # 无token时也能用，但限流更严
        )
        if token:
            self.api_key = token

    def _get_headers(self) -> Dict[str, str]:
        """构建请求头"""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Hubrium-MCP-Server",
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    async def fetch_raw(self, endpoint: str, params: Optional[Dict] = None, base_url_override: Optional[str] = None) -> Any:
        """获取原始数据"""
        return await self._make_request("GET", endpoint, params, base_url_override)

    def transform(self, raw_data: Any, data_type: str) -> Dict[str, Any]:
        """
        转换原始数据为标准格式

        Args:
            raw_data: GitHub API原始响应
            data_type: 数据类型 (dev_activity)

        Returns:
            标准化数据字典
        """
        if data_type == "dev_activity":
            return self._transform_dev_activity(raw_data)
        else:
            return raw_data

    def _transform_dev_activity(self, data: Dict) -> Dict:
        """
        转换开发活跃度数据（按Q4设计的指标）

        Expected data structure:
        {
            "repo": {...},
            "commits_30d": int,
            "commits_90d": int,
            "contributors": [...]
        }
        """
        repo_info = data.get("repo", {})
        commits_30d = data.get("commits_30d", 0)
        commits_90d = data.get("commits_90d", 0)
        contributors = data.get("contributors", [])

        # 计算活跃贡献者（30天内有提交）
        active_30d = len([c for c in contributors if c.get("recent_activity", False)])

        # 计算趋势
        trend = "stable"
        if commits_90d > 0:
            ratio_30_to_90 = commits_30d / (commits_90d / 3)  # 归一化到30天
            if ratio_30_to_90 > 1.2:
                trend = "increasing"
            elif ratio_30_to_90 < 0.8:
                trend = "decreasing"

        return {
            "commits_30d": commits_30d,
            "commits_90d": commits_90d,
            "contributors_active_30d": active_30d,
            "contributors_total": len(contributors),
            "last_commit_date": repo_info.get("pushed_at"),
            "repo_stars": repo_info.get("stargazers_count"),
            "repo_forks": repo_info.get("forks_count"),
            "trend": trend,
        }

    async def get_repo_info(self, owner: str, repo: str) -> Dict:
        """
        获取仓库基本信息

        Args:
            owner: 仓库所有者
            repo: 仓库名称

        Returns:
            仓库信息
        """
        endpoint = f"/repos/{owner}/{repo}"
        return await self.fetch_raw(endpoint)

    async def get_commits_count(
        self,
        owner: str,
        repo: str,
        since: datetime
    ) -> int:
        """
        获取指定时间后的commit数量

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            since: 起始时间

        Returns:
            commit数量
        """
        endpoint = f"/repos/{owner}/{repo}/commits"
        params = {
            "since": since.isoformat(),
            "per_page": 100,  # GitHub API最大值
        }

        try:
            # 获取第一页
            response = await self.fetch_raw(endpoint, params)

            # 如果少于100条，直接返回
            if len(response) < 100:
                return len(response)

            # 否则需要分页统计（简化：只统计前500条）
            total = len(response)
            page = 2

            while page <= 5 and total < 500:  # 最多5页
                params["page"] = page
                response = await self.fetch_raw(endpoint, params)

                if not response:
                    break

                total += len(response)
                page += 1

                if len(response) < 100:
                    break

            return total

        except Exception as e:
            logger.warning(f"Failed to get commits count", error=str(e))
            return 0

    async def get_contributors(self, owner: str, repo: str) -> list:
        """
        获取贡献者列表

        Args:
            owner: 仓库所有者
            repo: 仓库名称

        Returns:
            贡献者列表
        """
        endpoint = f"/repos/{owner}/{repo}/contributors"
        params = {
            "per_page": 100,
            "anon": "false",
        }

        try:
            return await self.fetch_raw(endpoint, params)
        except Exception as e:
            logger.warning(f"Failed to get contributors", error=str(e))
            return []

    async def get_dev_activity(self, owner: str, repo: str) -> Dict:
        """
        获取完整的开发活跃度数据

        Args:
            owner: 仓库所有者
            repo: 仓库名称

        Returns:
            开发活跃度数据
        """
        now = datetime.now(timezone.utc)
        days_30_ago = now - timedelta(days=30)
        days_90_ago = now - timedelta(days=90)

        # 并发获取数据（简化：顺序获取）
        repo_info = await self.get_repo_info(owner, repo)
        commits_30d = await self.get_commits_count(owner, repo, days_30_ago)
        commits_90d = await self.get_commits_count(owner, repo, days_90_ago)
        contributors = await self.get_contributors(owner, repo)

        return {
            "repo": repo_info,
            "commits_30d": commits_30d,
            "commits_90d": commits_90d,
            "contributors": contributors,
        }

    @staticmethod
    def parse_repo_url(url: str) -> Optional[tuple[str, str]]:
        """
        从GitHub URL解析owner和repo

        Args:
            url: GitHub URL (如 https://github.com/bitcoin/bitcoin)

        Returns:
            (owner, repo) 或 None
        """
        try:
            parts = url.rstrip("/").split("/")
            if "github.com" in url and len(parts) >= 2:
                return parts[-2], parts[-1]
            return None
        except Exception:
            return None
