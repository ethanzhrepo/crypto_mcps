"""
CryptoOverview工具单元测试
"""
import pytest

from src.core.models import Conflict, ConflictResolutionStrategy
from src.tools.crypto.overview import CryptoOverviewTool


@pytest.mark.unit
class TestCryptoOverviewTool:
    """CryptoOverview工具测试"""

    @pytest.fixture
    def tool(self):
        """创建工具实例"""
        return CryptoOverviewTool()

    def test_detect_price_conflict_within_threshold(self, tool):
        """测试价格差异在阈值内（≤0.5%）"""
        cg_data = {"price": 95000}
        cmc_data = {"price": 95100}  # 差异约0.105%

        conflict = tool._detect_price_conflict(cg_data, cmc_data)

        assert conflict is not None
        assert conflict.field == "price"
        assert conflict.resolution == ConflictResolutionStrategy.AVERAGE
        assert conflict.final_value == 95050  # 平均值

    def test_detect_price_conflict_above_threshold(self, tool):
        """测试价格差异超过阈值（>0.5%）"""
        cg_data = {"price": 95000}
        cmc_data = {"price": 96000}  # 差异约1.05%

        conflict = tool._detect_price_conflict(cg_data, cmc_data)

        assert conflict is not None
        assert conflict.field == "price"
        assert conflict.resolution == ConflictResolutionStrategy.PRIMARY_SOURCE
        assert conflict.final_value == 95000  # 主源优先

    def test_detect_price_conflict_no_data(self, tool):
        """测试无价格数据"""
        cg_data = {}
        cmc_data = {"price": 95000}

        conflict = tool._detect_price_conflict(cg_data, cmc_data)

        assert conflict is None

    def test_resolve_price_conflict(self, tool):
        """测试冲突解决"""
        cg_data = {"price": 95000, "market_cap": 1850000000000}
        cmc_data = {"price": 95100}

        conflict = Conflict(
            field="price",
            values={"coingecko": 95000, "coinmarketcap": 95100},
            diff_percent=0.105,
            diff_absolute=100,
            resolution=ConflictResolutionStrategy.AVERAGE,
            final_value=95050,
        )

        resolved_data = tool._resolve_price_conflict(cg_data, cmc_data, conflict)

        assert resolved_data["price"] == 95050
        assert resolved_data["market_cap"] == 1850000000000  # 其他字段不变

    def test_extract_github_url(self, tool):
        """测试GitHub URL提取"""
        urls = [
            "https://bitcoin.org",
            "https://github.com/bitcoin/bitcoin",
            "https://twitter.com/bitcoin",
        ]

        github_url = tool._extract_github_url(urls)

        assert github_url == "https://github.com/bitcoin/bitcoin"

    def test_extract_github_url_not_found(self, tool):
        """测试无GitHub URL"""
        urls = [
            "https://bitcoin.org",
            "https://twitter.com/bitcoin",
        ]

        github_url = tool._extract_github_url(urls)

        assert github_url is None
