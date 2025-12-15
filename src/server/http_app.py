"""
MCP HTTP REST API Server

提供 HTTP REST 接口访问多个 MCP 工具。
"""
import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Type

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from src.core.data_source_registry import registry
from src.core.models import (
    CryptoOverviewInput,
    CryptoOverviewOutput,
    DerivativesHubInput,
    DerivativesHubOutput,
    DrawChartInput,
    DrawChartOutput,
    GrokSocialTraceInput,
    GrokSocialTraceOutput,
    MacroHubInput,
    MacroHubOutput,
    MarketMicrostructureInput,
    MarketMicrostructureOutput,
    OnchainActivityInput,
    OnchainActivityOutput,
    OnchainBridgeVolumesInput,
    OnchainBridgeVolumesOutput,
    OnchainContractRiskInput,
    OnchainContractRiskOutput,
    OnchainDEXLiquidityInput,
    OnchainDEXLiquidityOutput,
    OnchainGovernanceInput,
    OnchainGovernanceOutput,
    OnchainStablecoinsCEXInput,
    OnchainStablecoinsCEXOutput,
    OnchainTVLFeesInput,
    OnchainTVLFeesOutput,
    OnchainTokenUnlocksInput,
    OnchainTokenUnlocksOutput,
    OnchainWhaleTransfersInput,
    OnchainWhaleTransfersOutput,
    TelegramSearchInput,
    TelegramSearchOutput,
    WebResearchInput,
    WebResearchOutput,
)
from src.data_sources.binance import BinanceClient
from src.data_sources.coingecko.client import CoinGeckoClient
from src.data_sources.coinmarketcap.client import CoinMarketCapClient
from src.data_sources.defillama import DefiLlamaClient
from src.data_sources.deribit import DeribitClient
from src.data_sources.etherscan.client import EtherscanClient
from src.data_sources.fred import FREDClient
from src.data_sources.github.client import GitHubClient
from src.data_sources.macro import MacroDataClient
from src.data_sources.okx import OKXClient
from src.data_sources.search import SearchClient
from src.data_sources.telegram_scraper import TelegramScraperClient
from src.data_sources.thegraph import TheGraphClient
from src.data_sources.yfinance import YahooFinanceClient
from src.data_sources.investing_calendar import InvestingCalendarClient
from src.middleware.cache import cache_manager
from src.tools.chart import DrawChartTool
from src.tools.crypto.overview import crypto_overview_tool
from src.tools.derivatives import DerivativesHubTool
from src.tools.grok_social_trace import GrokSocialTraceTool
from src.tools.macro import MacroHubTool
from src.tools.market import MarketMicrostructureTool
from src.tools.onchain.activity import OnchainActivityTool
from src.tools.onchain.bridge_volumes import OnchainBridgeVolumesTool
from src.tools.onchain.contract_risk import OnchainContractRiskTool
from src.tools.onchain.dex_liquidity import OnchainDEXLiquidityTool
from src.tools.onchain.governance import OnchainGovernanceTool
from src.tools.onchain.stablecoins_cex import OnchainStablecoinsCEXTool
from src.tools.onchain.token_unlocks import OnchainTokenUnlocksTool
from src.tools.onchain.tvl_fees import OnchainTVLFeesTool
from src.tools.onchain.whale_transfers import OnchainWhaleTransfersTool
from src.tools.telegram_search import TelegramSearchTool
from src.tools.web_research import WebResearchTool
from src.utils.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ==================== 全局工具实例 ====================
tools = {
    "crypto_overview": None,
    "market_microstructure": None,
    "derivatives_hub": None,
    "telegram_search": None,
    "web_research_search": None,
    "macro_hub": None,
    "draw_chart": None,
    "grok_social_trace": None,
    "onchain_tvl_fees": None,
    "onchain_stablecoins_cex": None,
    "onchain_bridge_volumes": None,
    "onchain_dex_liquidity": None,
    "onchain_governance": None,
    "onchain_whale_transfers": None,
    "onchain_token_unlocks": None,
    "onchain_activity": None,
    "onchain_contract_risk": None,
}


# ==================== 工具元数据与 registry 输出 ====================

def _compute_typical_ttl_seconds(tool_name: str) -> int:
    """Compute a representative TTL for the tool from ttl_policies.yaml."""
    try:
        tool_policy = config.ttl_policies.get(tool_name, {})
        if isinstance(tool_policy, dict) and tool_policy:
            values = [v for v in tool_policy.values() if isinstance(v, int) and v > 0]
            if values:
                return min(values)
        default_ttl = config.ttl_policies.get("default", 300)
        return default_ttl if isinstance(default_ttl, int) else 300
    except Exception:
        return 300


TOOL_SPECS: List[Dict[str, Any]] = [
    {
        "name": "crypto_overview",
        "description": "Comprehensive token overview including basic profile, market metrics, supply structure, holder concentration, social links, sector classification, and developer activity",
        "endpoint": "/tools/crypto_overview",
        "input_model": CryptoOverviewInput,
        "output_model": CryptoOverviewOutput,
        "capabilities": [
            "overview",
            "fundamentals",
            "market",
            "supply",
            "holders",
            "social",
            "sector",
            "dev_activity",
        ],
        "examples": [
            {
                "description": "BTC snapshot of fundamentals and market",
                "arguments": {"symbol": "BTC", "include_fields": ["basic", "market", "supply"]},
            }
        ],
        "limitations": [
            "Some fields require API keys: COINMARKETCAP_API_KEY (market ranking), ETHERSCAN_API_KEY (holders), GITHUB_TOKEN (dev_activity)."
        ],
        "cost_hints": {"latency_class": "medium"},
    },
    {
        "name": "market_microstructure",
        "description": "Real-time market microstructure data",
        "endpoint": "/tools/market_microstructure",
        "input_model": MarketMicrostructureInput,
        "output_model": MarketMicrostructureOutput,
        "capabilities": ["market", "microstructure", "liquidity", "volatility", "orderbook"],
        "examples": [
            {
                "description": "BTC/USDT ticker on Binance",
                "arguments": {"symbol": "BTC/USDT", "venues": ["binance"], "include_fields": ["ticker"]},
            }
        ],
        "limitations": [],
        "cost_hints": {"latency_class": "fast"},
    },
    {
        "name": "derivatives_hub",
        "description": "Derivatives data hub: funding rate, open interest, liquidations, long/short ratio, borrow rates, basis curve, term structure, options surface, and options metrics",
        "endpoint": "/tools/derivatives_hub",
        "input_model": DerivativesHubInput,
        "output_model": DerivativesHubOutput,
        "capabilities": [
            "derivatives",
            "funding_rate",
            "open_interest",
            "liquidations",
            "options",
            "basis",
            "term_structure",
        ],
        "examples": [
            {
                "description": "BTCUSDT funding and OI",
                "arguments": {"symbol": "BTCUSDT", "include_fields": ["funding_rate", "open_interest"]},
            }
        ],
        "limitations": [],
        "cost_hints": {"latency_class": "medium"},
    },
    {
        "name": "telegram_search",
        "description": "Search Telegram messages (Elasticsearch-backed) via Telegram Scraper",
        "endpoint": "/tools/telegram_search",
        "input_model": TelegramSearchInput,
        "output_model": TelegramSearchOutput,
        "capabilities": ["telegram", "news", "social", "narrative"],
        "examples": [
            {"description": "Search token mentions", "arguments": {"symbol": "BTC", "limit": 20, "time_range": "24h"}}
        ],
        "limitations": ["Requires TELEGRAM_SCRAPER_URL pointing to a reachable Telegram Scraper/Elasticsearch proxy."],
        "cost_hints": {"latency_class": "fast"},
    },
    {
        "name": "web_research_search",
        "description": "Multi-source web and news search: Bing News, Brave Search, Kaito crypto news, and DuckDuckGo. Supports parallel search with configurable providers",
        "endpoint": "/tools/web_research_search",
        "input_model": WebResearchInput,
        "output_model": WebResearchOutput,
        "capabilities": ["web", "news", "research", "narrative"],
        "examples": [
            {"description": "Search ETF approval news", "arguments": {"query": "BTC spot ETF approval", "top_k": 5}}
        ],
        "limitations": ["Providers may require API keys (see docker/.env)."],
        "cost_hints": {"latency_class": "slow"},
    },
    {
        "name": "macro_hub",
        "description": "Macro economic and market indicators: Fear & Greed Index, FRED data, traditional indices (S&P500, NASDAQ, VIX), commodities, economic calendar, and CME FedWatch tool",
        "endpoint": "/tools/macro_hub",
        "input_model": MacroHubInput,
        "output_model": MacroHubOutput,
        "capabilities": ["macro", "rates", "indices", "calendar"],
        "examples": [
            {"description": "Fetch Fear & Greed and DXY", "arguments": {"include_fields": ["fear_greed", "dxy"]}}
        ],
        "limitations": ["FRED fields require FRED_API_KEY when enabled."],
        "cost_hints": {"latency_class": "fast"},
    },
    {
        "name": "draw_chart",
        "description": "Chart visualization with Plotly based on client-provided configs: candlestick, line, area, bar, scatter. Does not fetch market data itself; callers must supply ready-to-render chart config.",
        "endpoint": "/tools/draw_chart",
        "input_model": DrawChartInput,
        "output_model": DrawChartOutput,
        "capabilities": ["chart", "visualization"],
        "examples": [
            {
                "description": "Render a line chart from provided Plotly config",
                "arguments": {
                    "chart_type": "line",
                    "symbol": "BTC/USDT",
                    "title": "BTC Price",
                    "config": {"data": [], "layout": {}},
                },
            }
        ],
        "limitations": ["Does not fetch data; input config must contain series."],
        "cost_hints": {"latency_class": "fast"},
    },
    {
        "name": "onchain_tvl_fees",
        "description": "On-chain DeFi metrics: protocol TVL and fees/revenue from DefiLlama.",
        "endpoint": "/tools/onchain_tvl_fees",
        "input_model": OnchainTVLFeesInput,
        "output_model": OnchainTVLFeesOutput,
        "capabilities": ["onchain", "defi", "tvl", "fees"],
        "examples": [{"description": "TVL for Uniswap", "arguments": {"protocol": "uniswap"}}],
        "limitations": [],
        "cost_hints": {"latency_class": "fast"},
    },
    {
        "name": "onchain_stablecoins_cex",
        "description": "Stablecoin metrics and centralized exchange reserves from DefiLlama.",
        "endpoint": "/tools/onchain_stablecoins_cex",
        "input_model": OnchainStablecoinsCEXInput,
        "output_model": OnchainStablecoinsCEXOutput,
        "capabilities": ["onchain", "stablecoins", "cex_reserves"],
        "examples": [{"description": "USDT supply and CEX reserves", "arguments": {"stablecoin": "USDT"}}],
        "limitations": [],
        "cost_hints": {"latency_class": "fast"},
    },
    {
        "name": "onchain_bridge_volumes",
        "description": "Cross-chain bridge volumes (24h/7d/30d) from DefiLlama.",
        "endpoint": "/tools/onchain_bridge_volumes",
        "input_model": OnchainBridgeVolumesInput,
        "output_model": OnchainBridgeVolumesOutput,
        "capabilities": ["onchain", "bridge", "crosschain"],
        "examples": [{"description": "Arbitrum bridge volumes", "arguments": {"chain": "arbitrum"}}],
        "limitations": [],
        "cost_hints": {"latency_class": "fast"},
    },
    {
        "name": "onchain_dex_liquidity",
        "description": "Uniswap v3 DEX liquidity, pools, and optional tick distribution from The Graph.",
        "endpoint": "/tools/onchain_dex_liquidity",
        "input_model": OnchainDEXLiquidityInput,
        "output_model": OnchainDEXLiquidityOutput,
        "capabilities": ["onchain", "dex", "liquidity"],
        "examples": [{"description": "ETH/USDC pool liquidity", "arguments": {"pool": "ETH/USDC"}}],
        "limitations": ["Supports Uniswap v3 pools via public subgraphs."],
        "cost_hints": {"latency_class": "medium"},
    },
    {
        "name": "onchain_governance",
        "description": "DAO governance proposals from Snapshot (off-chain) and Tally (on-chain).",
        "endpoint": "/tools/onchain_governance",
        "input_model": OnchainGovernanceInput,
        "output_model": OnchainGovernanceOutput,
        "capabilities": ["onchain", "governance", "dao"],
        "examples": [{"description": "Aave recent proposals", "arguments": {"dao": "aave", "top_k": 5}}],
        "limitations": ["Tally on-chain data may require TALLY_API_KEY for some DAOs."],
        "cost_hints": {"latency_class": "medium"},
    },
    {
        "name": "onchain_whale_transfers",
        "description": "Large on-chain transfers using Whale Alert API.",
        "endpoint": "/tools/onchain_whale_transfers",
        "input_model": OnchainWhaleTransfersInput,
        "output_model": OnchainWhaleTransfersOutput,
        "capabilities": ["onchain", "whales", "transfers"],
        "examples": [{"description": "Track large BTC transfers", "arguments": {"symbol": "BTC", "min_value_usd": 1000000}}],
        "limitations": ["WHALE_ALERT_API_KEY recommended for full coverage."],
        "cost_hints": {"latency_class": "fast"},
    },
    {
        "name": "onchain_token_unlocks",
        "description": "Token vesting and unlock schedules from Token Unlocks.",
        "endpoint": "/tools/onchain_token_unlocks",
        "input_model": OnchainTokenUnlocksInput,
        "output_model": OnchainTokenUnlocksOutput,
        "capabilities": ["tokenomics", "unlock", "supply"],
        "examples": [{"description": "Next unlocks for ARB", "arguments": {"symbol": "ARB"}}],
        "limitations": ["TOKEN_UNLOCKS_API_KEY required for some endpoints."],
        "cost_hints": {"latency_class": "fast"},
    },
    {
        "name": "onchain_activity",
        "description": "Chain-level activity metrics (active addresses, tx count, gas usage) from Etherscan.",
        "endpoint": "/tools/onchain_activity",
        "input_model": OnchainActivityInput,
        "output_model": OnchainActivityOutput,
        "capabilities": ["onchain", "activity", "addresses", "transactions"],
        "examples": [{"description": "Ethereum activity 7d", "arguments": {"chain": "ethereum", "window": "7d"}}],
        "limitations": ["ETHERSCAN_API_KEY required when querying Ethereum mainnet."],
        "cost_hints": {"latency_class": "medium"},
    },
    {
        "name": "onchain_contract_risk",
        "description": "Smart contract risk analysis via GoPlus or Slither.",
        "endpoint": "/tools/onchain_contract_risk",
        "input_model": OnchainContractRiskInput,
        "output_model": OnchainContractRiskOutput,
        "capabilities": ["risk", "security", "contract"],
        "examples": [
            {
                "description": "Analyze contract risk by address",
                "arguments": {"address": "0x0000000000000000000000000000000000000000", "chain": "ethereum"},
            }
        ],
        "limitations": ["GOPLUS_API_KEY/GOPLUS_API_SECRET required when provider=goplus."],
        "cost_hints": {"latency_class": "slow"},
    },
    {
        "name": "grok_social_trace",
        "description": "Trace the origin of a circulating message on X/Twitter using Grok, assess whether it is likely promotional, and provide deepsearch-based social analysis.",
        "endpoint": "/tools/grok_social_trace",
        "input_model": GrokSocialTraceInput,
        "output_model": GrokSocialTraceOutput,
        "capabilities": ["social", "narrative", "trace", "x/twitter"],
        "examples": [{"description": "Trace a rumor tweet", "arguments": {"text": "Some rumor text"}}],
        "limitations": ["Requires XAI_API_KEY and tool must be enabled in config/tools.yaml."],
        "cost_hints": {"latency_class": "slow"},
    },
]


def _enabled_tool_specs() -> List[Dict[str, Any]]:
    """Return enabled and initialized tool specs."""
    enabled: List[Dict[str, Any]] = []
    for spec in TOOL_SPECS:
        name = spec["name"]
        if not config.is_tool_enabled(name):
            continue
        if tools.get(name) is None:
            continue
        enabled.append(spec)
    return enabled


def _build_registry_entry(spec: Dict[str, Any]) -> Dict[str, Any]:
    input_model: Type[Any] = spec.get("input_model")
    output_model: Optional[Type[Any]] = spec.get("output_model")
    typical_ttl = _compute_typical_ttl_seconds(spec["name"])
    freshness = {
        "typical_ttl_seconds": typical_ttl,
        "as_of_semantics": (
            "Responses include as_of_utc and source_meta[].as_of_utc indicating data timestamp; "
            "ttl_seconds reflects cache freshness; conflicts/warnings may be present."
        ),
    }
    return {
        "name": spec["name"],
        "description": spec["description"],
        "endpoint": spec["endpoint"],
        "input_schema": input_model.model_json_schema() if input_model else None,
        "output_schema": output_model.model_json_schema() if output_model else None,
        "examples": spec.get("examples", []),
        "capabilities": spec.get("capabilities", []),
        "freshness": freshness,
        "limitations": spec.get("limitations", []),
        "cost_hints": spec.get("cost_hints", {}),
    }


# ==================== 生命周期管理 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("Starting MCP HTTP Server...")

    # 启动时初始化
    await initialize_data_sources()
    await initialize_tools()

    logger.info("MCP HTTP Server started successfully")

    yield

    # 关闭时清理
    logger.info("Shutting down MCP HTTP Server...")
    await cleanup()
    logger.info("MCP HTTP Server stopped")


async def initialize_data_sources():
    """初始化所有数据源"""
    logger.info("Registering data sources...")

    # Binance (交易所数据 - 主源)
    binance = BinanceClient()
    registry.register("binance", binance)

    # OKX (交易所数据 - 备用源)
    okx = OKXClient()
    registry.register("okx", okx)

    # DefiLlama (DeFi数据)
    defillama = DefiLlamaClient()
    registry.register("defillama", defillama)

    # Telegram Scraper (Telegram消息数据)
    telegram_scraper_client = None
    try:
        telegram_scraper_client = TelegramScraperClient(
            base_url=config.settings.telegram_scraper_url,
        )
        registry.register("telegram_scraper", telegram_scraper_client)
        logger.info(
            "telegram_scraper_client_initialized",
            url=config.settings.telegram_scraper_url,
        )
    except Exception as e:
        logger.warning(f"Failed to initialize Telegram Scraper client: {e}")

    # 加载新闻源配置
    news_source_config = None
    try:
        import yaml
        from pathlib import Path

        config_path = Path(__file__).parent.parent.parent / "config" / "data_sources.yaml"
        with open(config_path) as f:
            yaml_config = yaml.safe_load(f)
            news_source_config = yaml_config.get("web_research", {}).get("news_sources", {})
    except Exception as e:
        logger.warning(f"Failed to load news source config: {e}")

    # Search (搜索数据)
    brave_key = config.get_api_key("brave_search")
    bing_key = config.get_api_key("bing_search")
    kaito_key = config.get_api_key("kaito")
    search_client = SearchClient(
        brave_api_key=brave_key,
        bing_api_key=bing_key,
        kaito_api_key=kaito_key,
        news_source_config=news_source_config,
    )
    registry.register("search", search_client)

    # Macro Data (宏观数据 - 基础)
    macro_client = MacroDataClient()
    registry.register("macro", macro_client)

    # FRED (美联储经济数据)
    fred_key = config.get_api_key("fred")
    if fred_key:
        try:
            fred_client = FREDClient(api_key=fred_key)
            registry.register("fred", fred_client)
            logger.info("FRED client initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize FRED client: {e}")

    # Yahoo Finance (传统市场数据 - 免费无需key)
    try:
        yfinance_client = YahooFinanceClient()
        registry.register("yfinance", yfinance_client)
        logger.info("Yahoo Finance client initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize Yahoo Finance client: {e}")

    # Investing.com Calendar (财经日历 - 免费无需key，使用Playwright)
    try:
        # 获取Redis客户端用于calendar缓存
        redis_client = await cache_manager._get_redis()
        calendar_client = InvestingCalendarClient(redis_client=redis_client)
        registry.register("investing_calendar", calendar_client)
        logger.info("Investing.com Calendar client initialized successfully with Redis caching")
    except Exception as e:
        logger.warning(f"Failed to initialize Investing.com Calendar client: {e}")
        calendar_client = None  # 确保变量存在

    # The Graph (DEX流动性 - 免费公共子图)
    try:
        thegraph_client = TheGraphClient()
        registry.register("thegraph", thegraph_client)
        logger.info("The Graph client initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize The Graph client: {e}")

    # CoinGecko (加密货币市场数据)
    coingecko = CoinGeckoClient(api_key=config.get_api_key("coingecko"))
    registry.register("coingecko", coingecko)

    # Deribit (加密货币期权数据)
    deribit = DeribitClient()
    registry.register("deribit", deribit)

    # CoinMarketCap
    cmc_key = config.get_api_key("coinmarketcap")
    if cmc_key:
        cmc = CoinMarketCapClient(api_key=cmc_key)
        registry.register("coinmarketcap", cmc)

    # Etherscan
    etherscan_key = config.get_api_key("etherscan")
    if etherscan_key:
        etherscan = EtherscanClient(chain="ethereum", api_key=etherscan_key)
        registry.register("etherscan", etherscan)

    # GitHub
    github_token = config.get_api_key("github")
    github = GitHubClient(token=github_token)
    registry.register("github", github)

    logger.info(f"Registered {len(registry._sources)} data sources")


async def initialize_tools():
    """初始化所有工具"""
    logger.info("Initializing MCP tools...")

    binance = registry.get_source("binance")
    okx = registry.get_source("okx")
    coingecko = registry.get_source("coingecko")
    defillama = registry.get_source("defillama")
    thegraph = registry.get_source("thegraph")
    deribit = registry.get_source("deribit")
    search = registry.get_source("search")
    telegram_scraper = registry.get_source("telegram_scraper")
    macro = registry.get_source("macro")
    fred = registry.get_source("fred")
    yfinance = registry.get_source("yfinance")
    calendar = registry.get_source("investing_calendar")  # 从registry获取calendar_client

    # 初始化工具
    tools["market_microstructure"] = MarketMicrostructureTool(
        binance_client=binance,
        okx_client=okx,
        coingecko_client=coingecko,
    )
    tools["derivatives_hub"] = DerivativesHubTool(
        binance_client=binance,
        okx_client=okx,
        deribit_client=deribit,
    )
    tools["telegram_search"] = TelegramSearchTool(telegram_scraper_client=telegram_scraper)
    tools["web_research_search"] = WebResearchTool(search_client=search)
    tools["macro_hub"] = MacroHubTool(
        macro_client=macro,
        fred_client=fred,
        yfinance_client=yfinance,
        calendar_client=calendar,  # 从registry获取calendar客户端（带Redis缓存）
    )
    tools["draw_chart"] = DrawChartTool(market_tool=tools["market_microstructure"])
    tools["crypto_overview"] = crypto_overview_tool

    # Grok 社交媒体溯源工具
    xai_api_key = config.get_api_key("xai")
    if not xai_api_key:
        logger.warning(
            "grok_social_trace_api_key_missing",
            message="Grok Social Trace HTTP tool initialized without API key; endpoint will return error until configured.",
        )
    tools["grok_social_trace"] = GrokSocialTraceTool(api_key=xai_api_key)

    # 链上工具家族（拆分自原 onchain_hub）
    tools["onchain_tvl_fees"] = OnchainTVLFeesTool(defillama_client=defillama)
    tools["onchain_stablecoins_cex"] = OnchainStablecoinsCEXTool(
        defillama_client=defillama
    )
    tools["onchain_bridge_volumes"] = OnchainBridgeVolumesTool(
        defillama_client=defillama
    )
    tools["onchain_dex_liquidity"] = OnchainDEXLiquidityTool(thegraph_client=thegraph)
    tools["onchain_governance"] = OnchainGovernanceTool()
    tools["onchain_whale_transfers"] = OnchainWhaleTransfersTool()
    tools["onchain_token_unlocks"] = OnchainTokenUnlocksTool()
    tools["onchain_activity"] = OnchainActivityTool()
    tools["onchain_contract_risk"] = OnchainContractRiskTool()

    logger.info("All MCP tools initialized successfully", tools_count=len(tools))


async def cleanup():
    """清理资源"""
    logger.info("Cleaning up resources...")

    # 关闭所有数据源连接
    await registry.close_all()

    # 关闭Redis连接
    await cache_manager.close()

    logger.info("Cleanup completed")


# ==================== FastAPI 应用 ====================

app = FastAPI(
    title="Hubrium MCP Server",
    description="Crypto + Macro MCP Tools v3 - 多个域中心工具的 REST API",
    version="0.1.0",
    lifespan=lifespan,
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 健康检查 ====================

@app.get("/health")
async def health_check():
    """健康检查端点"""
    enabled_tools = _enabled_tool_specs()
    return {
        "status": "healthy",
        "service": "mcp-server",
        "version": "0.1.0",
        "tools_count": len(enabled_tools),
    }


@app.get("/")
async def root():
    """根路径"""
    return {
        "service": "Hubrium MCP Server",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "tools": "/tools",
    }


# ==================== 工具列表 ====================

@app.get("/tools")
async def list_tools():
    """列出所有可用的 MCP 工具"""
    return {
        "tools": [
            {
                "name": spec["name"],
                "description": spec["description"],
                "endpoint": spec["endpoint"],
            }
            for spec in _enabled_tool_specs()
        ]
    }


@app.get("/tools/definitions")
async def list_tool_definitions():
    """
    返回所有工具的详细定义（适合用于 LLM 动态加载）。

    该接口保留向后兼容，但会返回完整 registry entry，
    包含 input_schema/output_schema/examples/capabilities 等元信息。
    """
    return {"tools": [_build_registry_entry(spec) for spec in _enabled_tool_specs()]}


@app.get("/tools/registry")
async def list_tool_registry():
    """返回可执行级工具注册表（动态、仅包含启用工具）。"""
    return {"tools": [_build_registry_entry(spec) for spec in _enabled_tool_specs()]}


@app.get("/tools/{tool_name}")
async def get_tool_definition(tool_name: str):
    """按需返回单个工具的 registry entry。"""
    for spec in _enabled_tool_specs():
        if spec["name"] == tool_name:
            return _build_registry_entry(spec)
    raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found or disabled")


# ==================== 工具端点 ====================

@app.post("/tools/crypto_overview")
async def crypto_overview(params: CryptoOverviewInput):
    """Crypto Overview 工具"""
    try:
        tool = tools["crypto_overview"]
        if tool is None:
            raise HTTPException(status_code=503, detail="Tool not initialized")

        result = await tool.execute(params)
        return result.model_dump() if hasattr(result, 'model_dump') else result

    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"crypto_overview error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/market_microstructure")
async def market_microstructure(params: MarketMicrostructureInput):
    """Market Microstructure 工具"""
    try:
        tool = tools["market_microstructure"]
        if tool is None:
            raise HTTPException(status_code=503, detail="Tool not initialized")

        result = await tool.execute(params)
        return result.model_dump() if hasattr(result, 'model_dump') else result

    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"market_microstructure error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/derivatives_hub")
async def derivatives_hub(params: DerivativesHubInput):
    """Derivatives Hub 工具"""
    try:
        tool = tools["derivatives_hub"]
        if tool is None:
            raise HTTPException(status_code=503, detail="Tool not initialized")

        result = await tool.execute(params)
        return result.model_dump() if hasattr(result, 'model_dump') else result

    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"derivatives_hub error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/web_research_search")
async def web_research_search(params: WebResearchInput):
    """Web Research Search 工具"""
    try:
        tool = tools["web_research_search"]
        if tool is None:
            raise HTTPException(status_code=503, detail="Tool not initialized")

        result = await tool.execute(params)
        return result.model_dump() if hasattr(result, 'model_dump') else result

    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"web_research_search error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/telegram_search")
async def telegram_search(params: TelegramSearchInput):
    """Telegram Search 工具"""
    try:
        tool = tools["telegram_search"]
        if tool is None:
            raise HTTPException(status_code=503, detail="Tool not initialized")

        result = await tool.execute(params)
        return result.model_dump() if hasattr(result, 'model_dump') else result

    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("telegram_search error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/macro_hub")
async def macro_hub(params: MacroHubInput):
    """Macro Hub 工具"""
    try:
        tool = tools["macro_hub"]
        if tool is None:
            raise HTTPException(status_code=503, detail="Tool not initialized")

        result = await tool.execute(params)
        return result.model_dump() if hasattr(result, 'model_dump') else result

    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"macro_hub error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/draw_chart")
async def draw_chart(params: DrawChartInput):
    """Draw Chart 工具"""
    try:
        tool = tools["draw_chart"]
        if tool is None:
            raise HTTPException(status_code=503, detail="Tool not initialized")

        result = await tool.execute(params)
        return result.model_dump() if hasattr(result, 'model_dump') else result

    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"draw_chart error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/onchain_tvl_fees")
async def onchain_tvl_fees(params: OnchainTVLFeesInput):
    """Onchain TVL & Fees 工具"""
    try:
        tool = tools["onchain_tvl_fees"]
        if tool is None:
            raise HTTPException(status_code=503, detail="Tool not initialized")

        result = await tool.execute(params)
        return result.model_dump() if hasattr(result, "model_dump") else result
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("onchain_tvl_fees error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/onchain_stablecoins_cex")
async def onchain_stablecoins_cex(params: OnchainStablecoinsCEXInput):
    """Onchain Stablecoins & CEX Reserves 工具"""
    try:
        tool = tools["onchain_stablecoins_cex"]
        if tool is None:
            raise HTTPException(status_code=503, detail="Tool not initialized")

        result = await tool.execute(params)
        return result.model_dump() if hasattr(result, "model_dump") else result
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("onchain_stablecoins_cex error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/onchain_bridge_volumes")
async def onchain_bridge_volumes(params: OnchainBridgeVolumesInput):
    """Onchain Bridge Volumes 工具"""
    try:
        tool = tools["onchain_bridge_volumes"]
        if tool is None:
            raise HTTPException(status_code=503, detail="Tool not initialized")

        result = await tool.execute(params)
        return result.model_dump() if hasattr(result, "model_dump") else result
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("onchain_bridge_volumes error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/onchain_dex_liquidity")
async def onchain_dex_liquidity(params: OnchainDEXLiquidityInput):
    """Onchain DEX Liquidity 工具"""
    try:
        tool = tools["onchain_dex_liquidity"]
        if tool is None:
            raise HTTPException(status_code=503, detail="Tool not initialized")

        result = await tool.execute(params)
        return result.model_dump() if hasattr(result, "model_dump") else result
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("onchain_dex_liquidity error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/onchain_governance")
async def onchain_governance(params: OnchainGovernanceInput):
    """Onchain Governance 工具"""
    try:
        tool = tools["onchain_governance"]
        if tool is None:
            raise HTTPException(status_code=503, detail="Tool not initialized")

        result = await tool.execute(params)
        return result.model_dump() if hasattr(result, "model_dump") else result
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("onchain_governance error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/onchain_whale_transfers")
async def onchain_whale_transfers(params: OnchainWhaleTransfersInput):
    """Onchain Whale Transfers 工具"""
    try:
        tool = tools["onchain_whale_transfers"]
        if tool is None:
            raise HTTPException(status_code=503, detail="Tool not initialized")

        result = await tool.execute(params)
        return result.model_dump() if hasattr(result, "model_dump") else result
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("onchain_whale_transfers error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/onchain_token_unlocks")
async def onchain_token_unlocks(params: OnchainTokenUnlocksInput):
    """Onchain Token Unlocks 工具"""
    try:
        tool = tools["onchain_token_unlocks"]
        if tool is None:
            raise HTTPException(status_code=503, detail="Tool not initialized")

        result = await tool.execute(params)
        return result.model_dump() if hasattr(result, "model_dump") else result
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("onchain_token_unlocks error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/onchain_activity")
async def onchain_activity(params: OnchainActivityInput):
    """Onchain Activity 工具"""
    try:
        tool = tools["onchain_activity"]
        if tool is None:
            raise HTTPException(status_code=503, detail="Tool not initialized")

        result = await tool.execute(params)
        return result.model_dump() if hasattr(result, "model_dump") else result
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("onchain_activity error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/onchain_contract_risk")
async def onchain_contract_risk(params: OnchainContractRiskInput):
    """Onchain Contract Risk 工具"""
    try:
        tool = tools["onchain_contract_risk"]
        if tool is None:
            raise HTTPException(status_code=503, detail="Tool not initialized")

        result = await tool.execute(params)
        return result.model_dump() if hasattr(result, "model_dump") else result
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("onchain_contract_risk error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/grok_social_trace")
async def grok_social_trace(params: GrokSocialTraceInput):
    """Grok Social Trace 工具"""
    try:
        if not config.is_tool_enabled("grok_social_trace"):
            raise HTTPException(status_code=503, detail="Tool grok_social_trace disabled by configuration")

        tool = tools["grok_social_trace"]
        if tool is None:
            raise HTTPException(status_code=503, detail="Tool not initialized")

        result = await tool.execute(params)
        return result.model_dump() if hasattr(result, "model_dump") else result
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error("grok_social_trace error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 异常处理 ====================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    logger.error(f"Unhandled exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


# ==================== 主函数 ====================

def main():
    """启动 HTTP 服务器"""
    import uvicorn

    host = config.settings.http_host
    port = config.settings.http_port

    logger.info(f"Starting MCP HTTP Server on {host}:{port}")

    uvicorn.run(
        "src.server.http_app:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
