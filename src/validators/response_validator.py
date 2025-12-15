"""响应数据验证器

用于验证MCP工具返回的数据完整性，确保商用服务器质量。
"""
from typing import Dict, List

from src.core.models import MacroHubData, SearchResult


class ResponseValidator:
    """验证API响应数据完整性"""

    @staticmethod
    def validate_macro_hub(data: MacroHubData, mode: str) -> List[str]:
        """验证macro_hub响应数据

        Args:
            data: MacroHubData响应数据
            mode: 请求模式（dashboard/fed/indices/crypto_indices等）

        Returns:
            List[str]: 验证失败的问题列表，空列表表示验证通过
        """
        issues = []

        # 验证FED数据
        if mode in ["dashboard", "fed"]:
            if not data.fed or len(data.fed) == 0:
                issues.append("FED data is empty or null")

        # 验证传统指数
        if mode in ["dashboard", "indices"]:
            if not data.indices or len(data.indices) == 0:
                issues.append("Market indices are empty or null")

        # 验证加密指数
        if mode in ["dashboard", "crypto_indices"]:
            if not data.crypto_indices or len(data.crypto_indices) == 0:
                issues.append("Crypto indices are empty or null")

        # dashboard模式应该有所有数据
        if mode == "dashboard":
            if not data.fear_greed:
                issues.append("Fear & Greed index is null")

        return issues

    @staticmethod
    def validate_news_search(results: List[SearchResult], warnings: List[str]) -> Dict:
        """验证新闻搜索响应

        Args:
            results: 搜索结果列表
            warnings: 警告信息列表

        Returns:
            Dict: {is_valid: bool, reason: str}
        """
        # 如果结果为空但无warnings，说明静默失败
        if len(results) == 0 and len(warnings) == 0:
            return {
                "is_valid": False,
                "reason": "Empty results without any warnings indicates silent failure"
            }

        # 如果有结果，验证结构完整性
        if results:
            for i, r in enumerate(results[:3]):  # 检查前3个
                if not r.title:
                    return {
                        "is_valid": False,
                        "reason": f"Result {i} missing title"
                    }
                if not r.url:
                    return {
                        "is_valid": False,
                        "reason": f"Result {i} missing URL"
                    }

        return {"is_valid": True, "reason": "OK"}
