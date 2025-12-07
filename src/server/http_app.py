"""
MCP HTTP REST API Server

提供 HTTP REST 接口访问多个 MCP 工具。
"""
import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from src.core.data_source_registry import registry
from src.core.models import (
    CryptoOverviewInput,
    DerivativesHubInput,
    DrawChartInput,
    MacroHubInput,
    MarketMicrostructureInput,
    OnchainActivityInput,
    OnchainBridgeVolumesInput,
    OnchainContractRiskInput,
    OnchainDEXLiquidityInput,
    OnchainGovernanceInput,
    OnchainStablecoinsCEXInput,
    OnchainTVLFeesInput,
    OnchainTokenUnlocksInput,
    OnchainWhaleTransfersInput,
    WebResearchInput,
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
from src.middleware.cache import cache_manager
from src.tools.chart import DrawChartTool
from src.tools.crypto.overview import crypto_overview_tool
from src.tools.derivatives import DerivativesHubTool
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
from src.tools.web_research import WebResearchTool
from src.utils.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ==================== 全局工具实例 ====================
tools = {
    "crypto_overview": None,
    "market_microstructure": None,
    "derivatives_hub": None,
    "web_research_search": None,
    "macro_hub": None,
    "draw_chart": None,
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
            index_name=config.settings.telegram_scraper_index,
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
        telegram_scraper_client=telegram_scraper_client,
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
    macro = registry.get_source("macro")
    fred = registry.get_source("fred")
    yfinance = registry.get_source("yfinance")

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
    tools["web_research_search"] = WebResearchTool(search_client=search)
    tools["macro_hub"] = MacroHubTool(
        macro_client=macro,
        fred_client=fred,
        yfinance_client=yfinance,
        calendar_client=None,
    )
    tools["draw_chart"] = DrawChartTool(market_tool=tools["market_microstructure"])
    tools["crypto_overview"] = crypto_overview_tool

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
    return {
        "status": "healthy",
        "service": "mcp-server",
        "version": "0.1.0",
        "tools_count": len([t for t in tools.values() if t is not None]),
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
                "name": "crypto_overview",
                "description": "Comprehensive token overview including basic profile, market metrics, supply structure, holder concentration, social links, sector classification, and developer activity",
                "endpoint": "/tools/crypto_overview",
            },
            {
                "name": "market_microstructure",
                "description": "Real-time market microstructure data",
                "endpoint": "/tools/market_microstructure",
            },
            {
                "name": "derivatives_hub",
                "description": "Derivatives data hub: funding rate, open interest, liquidations, long/short ratio, borrow rates, basis curve, term structure, options surface, and options metrics",
                "endpoint": "/tools/derivatives_hub",
            },
            {
                "name": "web_research_search",
                "description": "Multi-source web and news search: Telegram messages, Bing News, Brave Search, Kaito crypto news, and DuckDuckGo. Supports parallel search with configurable providers",
                "endpoint": "/tools/web_research_search",
            },
            {
                "name": "macro_hub",
                "description": "Macro economic and market indicators: Fear & Greed Index, FRED data, traditional indices (S&P500, NASDAQ, VIX), commodities, economic calendar, and CME FedWatch tool",
                "endpoint": "/tools/macro_hub",
            },
            {
                "name": "draw_chart",
                "description": "Chart visualization with Plotly based on client-provided configs: candlestick, line, area, bar, scatter. Does not fetch market data itself; callers must supply ready-to-render chart config.",
                "endpoint": "/tools/draw_chart",
            },
            {
                "name": "onchain_tvl_fees",
                "description": "On-chain DeFi metrics: protocol TVL and fees/revenue from DefiLlama.",
                "endpoint": "/tools/onchain_tvl_fees",
            },
            {
                "name": "onchain_stablecoins_cex",
                "description": "Stablecoin metrics and centralized exchange reserves from DefiLlama.",
                "endpoint": "/tools/onchain_stablecoins_cex",
            },
            {
                "name": "onchain_bridge_volumes",
                "description": "Cross-chain bridge volumes (24h/7d/30d) from DefiLlama.",
                "endpoint": "/tools/onchain_bridge_volumes",
            },
            {
                "name": "onchain_dex_liquidity",
                "description": "Uniswap v3 DEX liquidity, pools, and optional tick distribution from The Graph.",
                "endpoint": "/tools/onchain_dex_liquidity",
            },
            {
                "name": "onchain_governance",
                "description": "DAO governance proposals from Snapshot (off-chain) and Tally (on-chain).",
                "endpoint": "/tools/onchain_governance",
            },
            {
                "name": "onchain_whale_transfers",
                "description": "Large on-chain transfers using Whale Alert API.",
                "endpoint": "/tools/onchain_whale_transfers",
            },
            {
                "name": "onchain_token_unlocks",
                "description": "Token vesting and unlock schedules from Token Unlocks.",
                "endpoint": "/tools/onchain_token_unlocks",
            },
            {
                "name": "onchain_activity",
                "description": "Chain-level activity metrics (active addresses, tx count, gas usage) from Etherscan.",
                "endpoint": "/tools/onchain_activity",
            },
            {
                "name": "onchain_contract_risk",
                "description": "Smart contract risk analysis via GoPlus or Slither.",
                "endpoint": "/tools/onchain_contract_risk",
            },
        ]
    }


@app.get("/tools/definitions")
async def list_tool_definitions():
    """
    返回所有工具的详细定义（适合用于 LLM 动态加载）：
    - name: 工具名
    - description: 简要说明
    - endpoint: 对应的 REST 调用路径
    - input_schema: 与 MCP list_tools 类似的 JSON Schema（来自 Pydantic Input 模型）
    """
    return {
        "tools": [
            {
                "name": "crypto_overview",
                "description": "Comprehensive token overview including basic profile, market metrics, supply structure, holder concentration, social links, sector classification, and developer activity",
                "endpoint": "/tools/crypto_overview",
                "input_schema": CryptoOverviewInput.model_json_schema(),
            },
            {
                "name": "market_microstructure",
                "description": "Real-time market microstructure data: ticker, klines, trades, orderbook depth, volume profile, taker flow, slippage estimation, and venue specifications.",
                "endpoint": "/tools/market_microstructure",
                "input_schema": MarketMicrostructureInput.model_json_schema(),
            },
            {
                "name": "derivatives_hub",
                "description": "Derivatives data hub: funding rate, open interest, liquidations, long/short ratio, borrow rates, basis curve, term structure, options surface, and options metrics.",
                "endpoint": "/tools/derivatives_hub",
                "input_schema": DerivativesHubInput.model_json_schema(),
            },
            {
                "name": "web_research_search",
                "description": "Multi-source web and news search: Telegram messages, Bing News, Brave Search, Kaito crypto news, and DuckDuckGo. Supports parallel search with configurable providers.",
                "endpoint": "/tools/web_research_search",
                "input_schema": WebResearchInput.model_json_schema(),
            },
            {
                "name": "macro_hub",
                "description": "Macro economic and market indicators: Fear & Greed Index, FRED data, traditional indices (S&P500, NASDAQ, VIX), commodities, economic calendar, and CME FedWatch tool.",
                "endpoint": "/tools/macro_hub",
                "input_schema": MacroHubInput.model_json_schema(),
            },
            {
                "name": "draw_chart",
                "description": "Chart normalization tool that accepts client-provided Plotly configs and returns chart metadata without fetching market data.",
                "endpoint": "/tools/draw_chart",
                "input_schema": DrawChartInput.model_json_schema(),
            },
            {
                "name": "onchain_tvl_fees",
                "description": "On-chain DeFi metrics: protocol TVL and fees/revenue from DefiLlama.",
                "endpoint": "/tools/onchain_tvl_fees",
                "input_schema": OnchainTVLFeesInput.model_json_schema(),
            },
            {
                "name": "onchain_stablecoins_cex",
                "description": "Stablecoin metrics and centralized exchange reserves from DefiLlama.",
                "endpoint": "/tools/onchain_stablecoins_cex",
                "input_schema": OnchainStablecoinsCEXInput.model_json_schema(),
            },
            {
                "name": "onchain_bridge_volumes",
                "description": "Cross-chain bridge volumes (24h/7d/30d) from DefiLlama.",
                "endpoint": "/tools/onchain_bridge_volumes",
                "input_schema": OnchainBridgeVolumesInput.model_json_schema(),
            },
            {
                "name": "onchain_dex_liquidity",
                "description": "Uniswap v3 DEX liquidity, pools, and optional tick distribution from The Graph.",
                "endpoint": "/tools/onchain_dex_liquidity",
                "input_schema": OnchainDEXLiquidityInput.model_json_schema(),
            },
            {
                "name": "onchain_governance",
                "description": "DAO governance proposals from Snapshot (off-chain) and Tally (on-chain).",
                "endpoint": "/tools/onchain_governance",
                "input_schema": OnchainGovernanceInput.model_json_schema(),
            },
            {
                "name": "onchain_whale_transfers",
                "description": "Large on-chain transfers using Whale Alert API.",
                "endpoint": "/tools/onchain_whale_transfers",
                "input_schema": OnchainWhaleTransfersInput.model_json_schema(),
            },
            {
                "name": "onchain_token_unlocks",
                "description": "Token vesting and unlock schedules from Token Unlocks.",
                "endpoint": "/tools/onchain_token_unlocks",
                "input_schema": OnchainTokenUnlocksInput.model_json_schema(),
            },
            {
                "name": "onchain_activity",
                "description": "Chain-level activity metrics (active addresses, tx count, gas usage) from Etherscan.",
                "endpoint": "/tools/onchain_activity",
                "input_schema": OnchainActivityInput.model_json_schema(),
            },
            {
                "name": "onchain_contract_risk",
                "description": "Smart contract risk analysis via GoPlus or Slither.",
                "endpoint": "/tools/onchain_contract_risk",
                "input_schema": OnchainContractRiskInput.model_json_schema(),
            },
        ]
    }


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
