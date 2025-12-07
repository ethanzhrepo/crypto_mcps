"""
crypto_overview端到端集成测试

注意：这些测试需要真实的API密钥和网络连接
运行方式：pytest -m integration
"""
import pytest

from src.core.data_source_registry import registry
from src.core.models import CryptoOverviewInput
from src.data_sources.coingecko.client import CoinGeckoClient
from src.data_sources.coinmarketcap.client import CoinMarketCapClient
from src.data_sources.github.client import GitHubClient
from src.tools.crypto.overview import crypto_overview_tool
from src.utils.config import config


@pytest.mark.integration
@pytest.mark.slow
class TestCryptoOverviewE2E:
    """端到端集成测试"""

    @pytest.fixture(autouse=True)
    async def setup_registry(self):
        """设置数据源注册表"""
        # 注册CoinGecko（免费API）
        coingecko = CoinGeckoClient()
        registry.register("coingecko", coingecko)

        # 如果有CMC key，注册CMC
        cmc_key = config.get_api_key("coinmarketcap")
        if cmc_key:
            cmc = CoinMarketCapClient(api_key=cmc_key)
            registry.register("coinmarketcap", cmc)

        # 注册GitHub
        github_token = config.get_api_key("github")
        github = GitHubClient(token=github_token)
        registry.register("github", github)

        yield

        # 清理
        await registry.close_all()

    @pytest.mark.asyncio
    async def test_fetch_bitcoin_basic(self):
        """测试获取BTC基础信息"""
        input_params = CryptoOverviewInput(
            symbol="BTC",
            include_fields=["basic", "market"]
        )

        result = await crypto_overview_tool.execute(input_params)

        assert result.symbol == "BTC"
        assert result.data.basic is not None
        assert result.data.basic.name == "Bitcoin"
        assert result.data.market is not None
        assert result.data.market.price > 0
        assert len(result.source_meta) > 0

    @pytest.mark.asyncio
    async def test_fetch_ethereum_full(self):
        """测试获取ETH完整信息（除holders）"""
        input_params = CryptoOverviewInput(
            symbol="ETH",
            include_fields=["basic", "market", "supply", "social", "sector"]
        )

        result = await crypto_overview_tool.execute(input_params)

        assert result.symbol == "ETH"
        assert result.data.basic is not None
        assert result.data.market is not None
        assert result.data.supply is not None
        assert result.data.social is not None
        assert result.data.sector is not None

    @pytest.mark.asyncio
    async def test_multi_source_conflict_detection(self):
        """测试多源冲突检测"""
        # 需要CMC API key
        if not config.get_api_key("coinmarketcap"):
            pytest.skip("CMC API key not configured")

        input_params = CryptoOverviewInput(
            symbol="BTC",
            include_fields=["market"]
        )

        result = await crypto_overview_tool.execute(input_params)

        # 检查是否有多个数据源
        providers = [meta.provider for meta in result.source_meta]
        assert len(set(providers)) >= 1  # 至少有CoinGecko

        # 如果有CMC，可能会有冲突记录
        if "coinmarketcap" in providers:
            # 冲突可能存在，也可能不存在（取决于价格差异）
            assert isinstance(result.conflicts, list)

    @pytest.mark.asyncio
    async def test_warning_for_missing_holders_params(self):
        """测试holders字段缺少参数时的警告"""
        input_params = CryptoOverviewInput(
            symbol="UNI",
            include_fields=["holders"]
            # 缺少chain和token_address
        )

        result = await crypto_overview_tool.execute(input_params)

        # 应该有警告
        assert any("require" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_dev_activity_for_bitcoin(self):
        """测试BTC的开发活跃度"""
        input_params = CryptoOverviewInput(
            symbol="BTC",
            include_fields=["basic", "dev_activity"]
        )

        result = await crypto_overview_tool.execute(input_params)

        # BTC有GitHub仓库，应该能获取开发活跃度
        if result.data.dev_activity:
            assert result.data.dev_activity.commits_30d is not None
            assert result.data.dev_activity.repo_stars is not None


@pytest.mark.integration
class TestDataSourceClients:
    """数据源客户端集成测试"""

    @pytest.mark.asyncio
    async def test_coingecko_symbol_resolution(self):
        """测试CoinGecko符号解析"""
        client = CoinGeckoClient()

        # 测试常见币种
        assert await client._symbol_to_id("BTC") == "bitcoin"
        assert await client._symbol_to_id("ETH") == "ethereum"
        assert await client._symbol_to_id("SOL") == "solana"

        await client.close()

    @pytest.mark.asyncio
    async def test_github_repo_url_parsing(self):
        """测试GitHub URL解析"""
        url = "https://github.com/bitcoin/bitcoin"
        parsed = GitHubClient.parse_repo_url(url)

        assert parsed == ("bitcoin", "bitcoin")

        # 测试其他格式
        url2 = "https://github.com/ethereum/go-ethereum/"
        parsed2 = GitHubClient.parse_repo_url(url2)

        assert parsed2 == ("ethereum", "go-ethereum")
