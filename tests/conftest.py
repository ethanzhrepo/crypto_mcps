"""
Pytest配置和共享fixtures
"""
import asyncio
import os
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from redis.asyncio import Redis

from src.core.data_source_registry import registry
from src.data_sources.binance import BinanceClient
from src.data_sources.coingecko.client import CoinGeckoClient
from src.data_sources.coinmarketcap.client import CoinMarketCapClient
from src.data_sources.cryptopanic import CryptoPanicClient
from src.data_sources.defillama import DefiLlamaClient
from src.data_sources.deribit import DeribitClient
from src.data_sources.etherscan.client import EtherscanClient
from src.data_sources.github.client import GitHubClient
from src.data_sources.macro import MacroDataClient
from src.data_sources.okx import OKXClient
from src.data_sources.search import SearchClient
from src.data_sources.snapshot import SnapshotClient
from src.data_sources.thegraph import TheGraphClient
from src.data_sources.twitter import TwitterClient
from src.utils.config import config


# ==================== Pytest Markers ====================

def pytest_configure(config):
    """注册自定义markers"""
    config.addinivalue_line("markers", "live: marks tests that call real APIs")
    config.addinivalue_line("markers", "live_free: marks tests using free APIs (no key required)")
    config.addinivalue_line("markers", "requires_key: marks tests requiring paid API keys")
    config.addinivalue_line("markers", "slow: marks tests as slow running")


# ==================== Data Source Registry Fixture ====================

@pytest.fixture(autouse=True)
def setup_registry():
    """
    为所有测试自动注册数据源到registry

    这确保Tool可以通过registry.get_source()获取客户端
    """
    # 清理之前的注册（避免测试间干扰）
    registry._sources.clear()

    # Binance (交易所数据 - 主源)
    binance = BinanceClient()
    registry.register("binance", binance)

    # OKX (交易所数据 - 备用源)
    okx = OKXClient()
    registry.register("okx", okx)

    # DefiLlama (DeFi数据)
    defillama = DefiLlamaClient()
    registry.register("defillama", defillama)

    # CryptoPanic (新闻数据)
    cryptopanic_key = config.get_api_key("cryptopanic")
    cryptopanic = CryptoPanicClient(api_key=cryptopanic_key)
    registry.register("cryptopanic", cryptopanic)

    # Search (搜索数据)
    brave_key = config.get_api_key("brave_search")
    search_client = SearchClient(brave_api_key=brave_key)
    registry.register("search", search_client)

    # Macro Data (宏观数据 - 基础)
    macro_client = MacroDataClient()
    registry.register("macro", macro_client)

    # The Graph (DEX流动性 - 免费公共子图)
    try:
        thegraph_client = TheGraphClient()
        registry.register("thegraph", thegraph_client)
    except Exception:
        pass

    # CoinGecko (加密货币市场数据)
    coingecko = CoinGeckoClient(
        api_key=config.get_api_key("coingecko"),
        api_type=getattr(config.settings, 'coingecko_api_type', 'demo') if hasattr(config, 'settings') else 'demo'
    )
    registry.register("coingecko", coingecko)

    # Deribit (加密货币期权数据)
    deribit = DeribitClient()
    registry.register("deribit", deribit)

    # Snapshot (治理数据)
    snapshot = SnapshotClient()
    registry.register("snapshot", snapshot)

    # Twitter (可选)
    twitter_token = config.get_api_key("twitter")
    if twitter_token:
        try:
            twitter_client = TwitterClient(bearer_token=twitter_token)
            registry.register("twitter", twitter_client)
        except Exception:
            pass

    # CoinMarketCap (可选)
    cmc_key = config.get_api_key("coinmarketcap")
    if cmc_key:
        try:
            cmc = CoinMarketCapClient(api_key=cmc_key)
            registry.register("coinmarketcap", cmc)
        except Exception:
            pass

    # Etherscan (可选)
    etherscan_key = config.get_api_key("etherscan")
    if etherscan_key:
        try:
            etherscan = EtherscanClient(chain="ethereum", api_key=etherscan_key)
            registry.register("etherscan", etherscan)
        except Exception:
            pass

    # GitHub
    github_token = config.get_api_key("github")
    github = GitHubClient(token=github_token)
    registry.register("github", github)

    yield

    # 清理
    registry._sources.clear()


# ==================== Live Test Fixtures ====================

@pytest.fixture
def is_live_test():
    """检查是否为真实API测试模式"""
    return os.getenv("TEST_MODE", "mock") == "live"


@pytest.fixture
def skip_if_no_key():
    """跳过需要API密钥的测试"""
    def _skip(key_name: str):
        key = os.getenv(key_name)
        if not key or key == "test-key":
            pytest.skip(f"{key_name} not configured for live tests")
    return _skip


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def mock_redis() -> AsyncGenerator[MagicMock, None]:
    """Mock Redis客户端"""
    redis_mock = MagicMock(spec=Redis)
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.setex = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=1)
    redis_mock.keys = AsyncMock(return_value=[])
    yield redis_mock


@pytest.fixture
def sample_coingecko_response():
    """示例CoinGecko API响应"""
    return {
        "id": "bitcoin",
        "symbol": "btc",
        "name": "Bitcoin",
        "description": {"en": "Bitcoin is a decentralized cryptocurrency..."},
        "links": {
            "homepage": ["https://bitcoin.org/"],
            "blockchain_site": ["https://blockchain.info/"],
        },
        "market_data": {
            "current_price": {"usd": 95000},
            "market_cap": {"usd": 1850000000000},
            "total_volume": {"usd": 45000000000},
            "circulating_supply": 19500000,
            "total_supply": 21000000,
            "max_supply": 21000000,
        },
        "community_data": {
            "twitter_followers": 5800000,
        },
    }


@pytest.fixture
def sample_coinmarketcap_response():
    """示例CoinMarketCap API响应"""
    return {
        "data": {
            "BTC": {
                "id": 1,
                "name": "Bitcoin",
                "symbol": "BTC",
                "quote": {
                    "USD": {
                        "price": 95100,
                        "market_cap": 1855000000000,
                        "volume_24h": 46000000000,
                    }
                },
                "circulating_supply": 19500000,
                "total_supply": 19500000,
                "max_supply": 21000000,
            }
        }
    }


@pytest.fixture
def sample_etherscan_response():
    """示例Etherscan API响应"""
    return {
        "status": "1",
        "message": "OK",
        "result": [
            {"account": "0x1234...", "balance": "1000000000000000000"},
            {"account": "0x5678...", "balance": "500000000000000000"},
        ],
    }


@pytest.fixture
def mock_httpx_client():
    """Mock HTTPX客户端"""
    client = MagicMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock()
    return client


@pytest.fixture
def sample_search_result():
    """示例搜索结果"""
    return {
        "title": "Bitcoin Documentation",
        "url": "https://bitcoin.org/en/developer-documentation",
        "snippet": "Bitcoin uses peer-to-peer technology to operate with no central authority",
        "source": "Google",
        "relevance_score": None,
    }


@pytest.fixture
def sample_kline_data():
    """示例K线数据"""
    return [
        {
            "open_time": 1700308800000,
            "close_time": 1700312400000,
            "open": 95000.0,
            "high": 95500.0,
            "low": 94800.0,
            "close": 95200.0,
            "volume": 123.45,
            "quote_volume": 11734560.0,
            "trades_count": 1500,
        },
        {
            "open_time": 1700312400000,
            "close_time": 1700316000000,
            "open": 95200.0,
            "high": 95800.0,
            "low": 95100.0,
            "close": 95600.0,
            "volume": 150.67,
            "quote_volume": 14400000.0,
            "trades_count": 1800,
        },
    ]


@pytest.fixture
def sample_fear_greed_response():
    """示例恐惧贪婪指数响应"""
    return {
        "value": 75,
        "value_classification": "Greed",
        "timestamp": "2025-11-18T12:00:00Z",
        "time_until_update": "12 hours",
    }


@pytest.fixture
def sample_funding_rate_response():
    """示例资金费率响应"""
    return {
        "symbol": "BTCUSDT",
        "exchange": "binance",
        "current_funding_rate": 0.0001,
        "next_funding_time": "2025-11-18T16:00:00Z",
        "avg_funding_rate_8h": 0.00012,
        "avg_funding_rate_24h": 0.00015,
    }


@pytest.fixture
def sample_tvl_response():
    """示例TVL响应"""
    return {
        "protocol": "uniswap",
        "tvl_usd": 5000000000.0,
        "chains": {
            "ethereum": 3000000000.0,
            "arbitrum": 1000000000.0,
            "polygon": 500000000.0,
        },
        "change_24h": 2.5,
        "timestamp": "2025-11-18T12:00:00Z",
    }
