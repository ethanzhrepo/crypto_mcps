"""
MCP服务器主程序
"""
import asyncio
import os
import signal
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server

from src.core.data_source_registry import registry
from src.core.models import (
    CryptoOverviewInput,
    EtfFlowsHoldingsInput,
    CexNetflowReservesInput,
    LendingLiquidationRiskInput,
    StablecoinHealthInput,
    OptionsVolSkewInput,
    BlockspaceMevInput,
    HyperliquidMarketInput,
    DerivativesHubInput,
    GrokSocialTraceInput,
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
    CryptoNewsSearchInput,
    WebResearchInput,
    # 新增工具模型
    PriceHistoryInput,
    SectorPeersInput,
    SentimentAggregatorInput,
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
from src.data_sources.cme.fedwatch import CMEFedWatchClient
from src.middleware.cache import cache_manager
from src.tools.blockspace_mev import BlockspaceMevTool
from src.tools.cex_netflow_reserves import CexNetflowReservesTool
from src.tools.crypto.overview import crypto_overview_tool
from src.tools.derivatives import DerivativesHubTool
from src.tools.etf_flows_holdings import EtfFlowsHoldingsTool
from src.tools.grok_social_trace import GrokSocialTraceTool
from src.tools.hyperliquid_market import HyperliquidMarketTool
from src.tools.lending_liquidation_risk import LendingLiquidationRiskTool
from src.tools.macro import MacroHubTool
from src.tools.market import MarketMicrostructureTool, PriceHistoryTool, SectorPeersTool
from src.tools.sentiment import SentimentAggregatorTool
from src.tools.options_vol_skew import OptionsVolSkewTool
from src.tools.onchain.activity import OnchainActivityTool
from src.tools.onchain.bridge_volumes import OnchainBridgeVolumesTool
from src.tools.onchain.contract_risk import OnchainContractRiskTool
from src.tools.onchain.dex_liquidity import OnchainDEXLiquidityTool
from src.tools.onchain.governance import OnchainGovernanceTool
from src.tools.onchain.stablecoins_cex import OnchainStablecoinsCEXTool
from src.tools.onchain.token_unlocks import OnchainTokenUnlocksTool
from src.tools.onchain.tvl_fees import OnchainTVLFeesTool
from src.tools.stablecoin_health import StablecoinHealthTool
from src.tools.crypto_news_search import CryptoNewsSearchTool
from src.tools.web_research import WebResearchTool
from src.utils.config import config
from src.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


class MCPServer:
    """MCP服务器"""

    def __init__(self):
        self.server = Server("hubrium-mcp-server")
        self._shutdown = False
        self.market_microstructure_tool = None
        self.derivatives_hub_tool = None
        self.web_research_tool = None
        self.crypto_news_search_tool = None
        self.macro_hub_tool = None
        self.grok_social_trace_tool = None
        self.etf_flows_holdings_tool = None
        self.cex_netflow_reserves_tool = None
        self.lending_liquidation_risk_tool = None
        self.stablecoin_health_tool = None
        self.options_vol_skew_tool = None
        self.blockspace_mev_tool = None
        self.hyperliquid_market_tool = None
        # 链上工具（拆分自原 onchain_hub）
        self.onchain_tvl_fees_tool = None
        self.onchain_stablecoins_cex_tool = None
        self.onchain_bridge_volumes_tool = None
        self.onchain_dex_liquidity_tool = None
        self.onchain_governance_tool = None
        self.onchain_token_unlocks_tool = None
        self.onchain_activity_tool = None
        self.onchain_contract_risk_tool = None
        # 新增工具
        self.price_history_tool = None
        self.sector_peers_tool = None
        self.sentiment_aggregator_tool = None

    async def initialize(self):
        """初始化服务器"""
        logger.info("Initializing MCP server...")

        # 注册数据源
        await self._register_data_sources()

        # 注册工具
        self._register_tools()

        logger.info("MCP server initialized successfully")

    async def _register_data_sources(self):
        """注册所有数据源到Registry"""
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

        # Telegram Scraper 数据源
        telegram_scraper_client = None
        try:
            telegram_scraper_client = TelegramScraperClient(
                base_url=config.settings.telegram_scraper_url,
                verify_ssl=False,  # 支持自签名证书
            )
            registry.register("telegram_scraper", telegram_scraper_client)
            logger.info(
                "crypto_news_search_client_initialized",
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
        fred_client = None
        fred_key = config.get_api_key("fred")
        if fred_key:
            try:
                fred_client = FREDClient(api_key=fred_key)
                registry.register("fred", fred_client)
                logger.info("FRED client initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize FRED client: {e}")
        else:
            logger.warning(
                "FRED API key not configured. Macro data will be limited. "
                "Get free key at: https://fredaccount.stlouisfed.org/apikeys"
            )

        # Yahoo Finance (传统市场数据 - 免费无需key)
        yfinance_client = None
        try:
            yfinance_client = YahooFinanceClient()
            registry.register("yfinance", yfinance_client)
            logger.info("Yahoo Finance client initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize Yahoo Finance client: {e}")

        # Investing.com Calendar (财经日历 - 免费无需key)
        calendar_client = None
        try:
            calendar_client = InvestingCalendarClient()
            registry.register("investing_calendar", calendar_client)
            logger.info("Investing.com calendar client initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize Investing.com calendar client: {e}")

        # The Graph (DEX流动性 - 免费公共子图)
        thegraph_client = None
        try:
            thegraph_client = TheGraphClient()
            registry.register("thegraph", thegraph_client)
            logger.info("The Graph client initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize The Graph client: {e}")

        # CoinGecko (加密货币市场数据 - 免费/Pro可选)
        coingecko = CoinGeckoClient(api_key=config.get_api_key("coingecko"))
        registry.register("coingecko", coingecko)

        # Deribit (加密货币期权数据 - 免费公共数据)
        deribit = DeribitClient()
        registry.register("deribit", deribit)

        # 初始化所有工具（按依赖顺序）
        self.market_microstructure_tool = MarketMicrostructureTool(
            binance_client=binance,
            okx_client=okx,
            coingecko_client=coingecko,
        )
        self.derivatives_hub_tool = DerivativesHubTool(
            binance_client=binance,
            okx_client=okx,
            deribit_client=deribit,
        )
        self.web_research_tool = WebResearchTool(search_client=search_client)
        self.crypto_news_search_tool = CryptoNewsSearchTool(
            telegram_scraper_client=telegram_scraper_client
        )
        # FedWatch client (CME利率预期)
        fedwatch_client = CMEFedWatchClient()
        self.macro_hub_tool = MacroHubTool(
            macro_client=macro_client,
            fred_client=fred_client,
            yfinance_client=yfinance_client,
            calendar_client=calendar_client,
            fedwatch_client=fedwatch_client,
        )
        # Grok 社交媒体溯源工具（仅在配置启用时可被调用）
        xai_api_key = os.getenv("XAI_API_KEY")
        self.grok_social_trace_tool = GrokSocialTraceTool(api_key=xai_api_key)
        # 新增数据工具
        self.etf_flows_holdings_tool = EtfFlowsHoldingsTool()
        self.cex_netflow_reserves_tool = CexNetflowReservesTool()
        self.lending_liquidation_risk_tool = LendingLiquidationRiskTool()
        self.stablecoin_health_tool = StablecoinHealthTool()
        self.options_vol_skew_tool = OptionsVolSkewTool()
        self.blockspace_mev_tool = BlockspaceMevTool()
        self.hyperliquid_market_tool = HyperliquidMarketTool()

        # 链上数据工具家族（拆分自原 onchain_hub）
        self.onchain_tvl_fees_tool = OnchainTVLFeesTool(defillama_client=defillama)
        self.onchain_stablecoins_cex_tool = OnchainStablecoinsCEXTool(
            defillama_client=defillama
        )
        self.onchain_bridge_volumes_tool = OnchainBridgeVolumesTool(
            defillama_client=defillama
        )
        self.onchain_dex_liquidity_tool = OnchainDEXLiquidityTool(
            thegraph_client=thegraph_client
        )
        self.onchain_governance_tool = OnchainGovernanceTool()
        self.onchain_token_unlocks_tool = OnchainTokenUnlocksTool()
        self.onchain_activity_tool = OnchainActivityTool()
        self.onchain_contract_risk_tool = OnchainContractRiskTool()

        # 新增工具初始化
        self.price_history_tool = PriceHistoryTool(
            binance_client=binance,
            okx_client=okx,
        )
        self.sector_peers_tool = SectorPeersTool(
            coingecko_client=coingecko,
            defillama_client=defillama,
        )
        self.sentiment_aggregator_tool = SentimentAggregatorTool(
            crypto_news_search_tool=self.crypto_news_search_tool,
            grok_social_trace_tool=self.grok_social_trace_tool,
            web_research_tool=self.web_research_tool,
        )

        # CoinMarketCap
        cmc_key = config.get_api_key("coinmarketcap")
        if cmc_key:
            cmc = CoinMarketCapClient(api_key=cmc_key)
            registry.register("coinmarketcap", cmc)
        else:
            logger.warning("CoinMarketCap API key not configured, skipping")

        # Etherscan (主网)
        etherscan_key = config.get_api_key("etherscan")
        if etherscan_key:
            etherscan = EtherscanClient(chain="ethereum", api_key=etherscan_key)
            registry.register("etherscan", etherscan)
        else:
            logger.warning("Etherscan API key not configured, skipping")

        # GitHub
        github_token = config.get_api_key("github")
        github = GitHubClient(token=github_token)
        registry.register("github", github)

        logger.info(f"Registered {len(registry._sources)} data sources")
        logger.info("All MCP tools initialized successfully")

    def _register_tools(self):
        """注册MCP工具"""
        logger.info("Registering MCP tools...")

        @self.server.list_tools()
        async def list_tools() -> list[dict]:
            tools: list[dict] = []

            """
            if config.is_tool_enabled("crypto_overview"):
                tools.append(
                    {
                        "name": "crypto_overview",
                        "description": "One-shot comprehensive token overview: basic profile, market metrics, supply, holder concentration, social links, sector classification, and developer activity.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "Token symbol, e.g. BTC, ETH, ARB"
                            },
                            "token_address": {
                                "type": "string",
                                "description": "Contract address (optional, for disambiguation)"
                            },
                            "chain": {
                                "type": "string",
                                "description": "Chain name, e.g. ethereum, bsc, arbitrum"
                            },
                            "vs_currency": {
                                "type": "string",
                                "default": "usd",
                                "description": "Quote currency"
                            },
                            "include_fields": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "enum": ["all", "basic", "market", "supply", "holders", "social", "sector", "dev_activity"]
                                },
                                "default": ["all"],
                                "description": "Fields to include"
                            }
                        },
                        "required": ["symbol"]
                    },
                )

            if config.is_tool_enabled("market_microstructure"):
                tools.append(
                    {
                        "name": "market_microstructure",
                    "description": "Real-time market microstructure data: ticker, klines, trades, orderbook depth, volume profile, taker flow, slippage estimation, and venue specifications.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "Trading pair symbol, e.g. BTC/USDT, ETH/USDT"
                            },
                            "venues": {
                                "type": "array",
                                "items": {"type": "string"},
                                "default": ["binance"],
                                "description": "List of venues/exchanges, e.g. ['binance', 'okx']; first one is used as primary venue"
                            },
                            "include_fields": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "enum": ["ticker", "klines", "trades", "orderbook", "volume_profile", "taker_flow", "slippage", "venue_specs", "sector_stats"]
                                },
                                "default": ["ticker", "orderbook"],
                                "description": "Fields to include"
                            },
                            "kline_interval": {
                                "type": "string",
                                "default": "1h",
                                "description": "K-line interval: 1m, 5m, 15m, 1h, 4h, 1d"
                            },
                            "kline_limit": {
                                "type": "integer",
                                "default": 100,
                                "description": "Number of K-lines"
                            },
                            "orderbook_depth": {
                                "type": "integer",
                                "default": 20,
                                "description": "Orderbook depth levels"
                            },
                            "trades_limit": {
                                "type": "integer",
                                "default": 100,
                                "description": "Number of recent trades"
                            },
                            "slippage_size_usd": {
                                "type": "number",
                                "default": 10000,
                                "description": "Order size for slippage estimation (USD)"
                            }
                        },
                        "required": ["symbol"]
                    },
                )

            if config.is_tool_enabled("derivatives_hub"):
                tools.append(
                    {
                    "name": "derivatives_hub",
                    "description": "Derivatives data hub: funding rate, open interest, liquidations, long/short ratio, borrow rates, basis curve, term structure, options surface, and options metrics.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "Trading pair symbol, e.g. BTC/USDT, ETH/USDT"
                            },
                            "include_fields": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "enum": ["funding_rate", "open_interest", "liquidations", "long_short_ratio", "basis_curve", "term_structure", "options_surface", "options_metrics", "borrow_rates"]
                                },
                                "default": ["funding_rate", "open_interest"],
                                "description": "Fields to include"
                            },
                            "lookback_hours": {
                                "type": "integer",
                                "default": 24,
                                "description": "Lookback hours for liquidation data"
                            },
                            "options_expiry": {
                                "type": "string",
                                "description": "Options expiry date (YYMMDD format)"
                            }
                        },
                        "required": ["symbol"]
                    },
                )

            if config.is_tool_enabled("onchain_tvl_fees"):
                tools.append(
                    {
                    "name": "onchain_tvl_fees",
                    "description": "On-chain DeFi metrics: protocol TVL and fees/revenue from DefiLlama.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "protocol": {
                                "type": "string",
                                "description": "Protocol name, e.g. uniswap, aave"
                            },
                            "chain": {
                                "type": "string",
                                "description": "Optional chain label, e.g. ethereum, arbitrum"
                            }
                        },
                        "required": ["protocol"]
                    }
                },
                {
                    "name": "onchain_stablecoins_cex",
                    "description": "Stablecoin metrics and centralized exchange reserves from DefiLlama.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "exchange": {
                                "type": "string",
                                "description": "Optional CEX name, e.g. binance, coinbase; if omitted returns aggregated view"
                            }
                        },
                        "required": []
                    }
                },
                {
                    "name": "onchain_bridge_volumes",
                    "description": "Cross-chain bridge volumes (24h/7d/30d) from DefiLlama.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "bridge": {
                                "type": "string",
                                "description": "Optional bridge name, e.g. stargate, hop; if omitted returns aggregated view"
                            }
                        },
                        "required": []
                    }
                },
                {
                    "name": "onchain_dex_liquidity",
                    "description": "Uniswap v3 DEX liquidity, pools, and optional tick distribution from The Graph.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "chain": {
                                "type": "string",
                                "description": "Chain name, e.g. ethereum, arbitrum, optimism, polygon"
                            },
                            "token_address": {
                                "type": "string",
                                "description": "Optional token address to list related pools"
                            },
                            "pool_address": {
                                "type": "string",
                                "description": "Optional Uniswap v3 pool address for single-pool detail"
                            },
                            "include_ticks": {
                                "type": "boolean",
                                "default": False,
                                "description": "Whether to include tick-level liquidity distribution (only valid with pool_address)"
                            }
                        },
                        "required": ["chain"]
                    },
                )

            if config.is_tool_enabled("onchain_contract_risk"):
                tools.append(
                {
                    "name": "onchain_governance",
                    "description": "DAO governance proposals from Snapshot (off-chain) and Tally (on-chain).",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "chain": {
                                "type": "string",
                                "default": "ethereum",
                                "description": "Chain name used to derive Tally chain_id, e.g. ethereum, arbitrum"
                            },
                            "snapshot_space": {
                                "type": "string",
                                "description": "Snapshot space id, e.g. uniswap.eth"
                            },
                            "governor_address": {
                                "type": "string",
                                "description": "On-chain governor contract address for Tally"
                            }
                        },
                        "required": []
                    }
                },
                {
                    "name": "onchain_token_unlocks",
                    "description": "Token vesting and unlock schedules from Token Unlocks.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "token_symbol": {
                                "type": "string",
                                "description": "Optional token symbol; if omitted returns popular projects unlocks"
                            }
                        },
                        "required": []
                    }
                },
                {
                    "name": "onchain_activity",
                    "description": "Chain-level activity metrics (active addresses, tx count, gas usage) from Etherscan.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "chain": {
                                "type": "string",
                                "description": "Chain name, e.g. ethereum, arbitrum, optimism, polygon"
                            },
                            "protocol": {
                                "type": "string",
                                "description": "Optional protocol label used only for tagging"
                            }
                        },
                        "required": ["chain"]
                    }
                },
                {
                    "name": "onchain_contract_risk",
                    "description": "Smart contract risk analysis via GoPlus or Slither.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "contract_address": {
                                "type": "string",
                                "description": "Contract address to analyze"
                            },
                            "chain": {
                                "type": "string",
                                "description": "Chain name, e.g. ethereum, arbitrum, optimism, polygon"
                            },
                            "provider": {
                                "type": "string",
                                "description": "Optional provider override: goplus or slither"
                            }
                        },
                        "required": ["contract_address", "chain"]
                    },
                )

            if config.is_tool_enabled("web_research_search"):
                tools.append(
                    {
                        "name": "web_research_search",
                    "description": "Multi-source web and news search: Bing News, Brave Search, Kaito crypto news, and DuckDuckGo. Supports parallel search with configurable providers and result merging.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "scope": {
                                "type": "string",
                                "enum": ["web", "news", "academic"],
                                "default": "web",
                                "description": "Search scope: web (general), news (crypto news from multiple sources), academic (research papers)"
                            },
                            "providers": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Specific providers to use (optional, e.g., ['bing_news', 'kaito', 'brave'])"
                            },
                            "time_range": {
                                "type": "string",
                                "description": "Time filter for news (e.g., '24h', '7d', '30d')"
                            },
                            "limit": {"type": "integer", "default": 10, "description": "Maximum results to return"}
                        },
                        "required": ["query"]
                    },
                )

            if config.is_tool_enabled("macro_hub"):
                tools.append(
                    {
                    "name": "macro_hub",
                    "description": "Macro economic and market indicators: Fear & Greed Index, FRED data (CPI, unemployment, GDP, rates), traditional indices (S&P500, NASDAQ, VIX), commodities (gold, oil), economic calendar, and CME FedWatch tool.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "mode": {
                                "type": "string",
                                "enum": ["dashboard", "fear_greed", "crypto_indices", "indices", "fed", "calendar"],
                                "default": "dashboard",
                                "description": "Query mode: dashboard (overview), or one of fear_greed, crypto_indices, indices, fed, calendar"
                            },
                            "country": {
                                "type": "string",
                                "default": "US",
                                "description": "Country code for macro calendar, e.g. US"
                            },
                            "calendar_days": {
                                "type": "integer",
                                "default": 7,
                                "description": "Number of days ahead for economic calendar (used when mode=calendar or dashboard)"
                            },
                            "calendar_min_importance": {
                                "type": "integer",
                                "default": 2,
                                "description": "Minimum importance level (1-3) for calendar events"
                            }
                        },
                        "required": []
                    },
                )

            if config.is_tool_enabled("grok_social_trace"):
                tools.append(
                    {
                        "name": "grok_social_trace",
                        "description": "Trace the origin of a circulating message on X/Twitter using Grok, assess whether it is likely promotional, and provide deepsearch-based social analysis.",
                        "input_schema": GrokSocialTraceInput.model_json_schema(),
                    }
                )

            """

            # New simplified tool registry using Pydantic schemas and config switches

            def add_tool(name: str, description: str, schema_model) -> None:
                if not config.is_tool_enabled(name):
                    return
                tools.append(
                    {
                        "name": name,
                        "description": description,
                        "input_schema": schema_model.model_json_schema(),
                    }
                )

            add_tool(
                "crypto_overview",
                "One-shot comprehensive token overview: basic profile, market metrics, supply, holder concentration, social links, sector classification, and developer activity.",
                CryptoOverviewInput,
            )
            add_tool(
                "market_microstructure",
                "Real-time market microstructure data: ticker, klines, trades, orderbook depth, volume profile, taker flow, slippage estimation, and venue specifications.",
                MarketMicrostructureInput,
            )
            add_tool(
                "derivatives_hub",
                "Derivatives data hub: funding rate, open interest, liquidations, long/short ratio, borrow rates, basis curve, term structure, options surface, and options metrics.",
                DerivativesHubInput,
            )
            add_tool(
                "onchain_tvl_fees",
                "On-chain DeFi metrics: protocol TVL and fees/revenue from DefiLlama.",
                OnchainTVLFeesInput,
            )
            add_tool(
                "onchain_stablecoins_cex",
                "Stablecoin metrics and centralized exchange reserves from DefiLlama.",
                OnchainStablecoinsCEXInput,
            )
            add_tool(
                "onchain_bridge_volumes",
                "Cross-chain bridge volumes (24h/7d/30d) from DefiLlama.",
                OnchainBridgeVolumesInput,
            )
            add_tool(
                "onchain_dex_liquidity",
                "Uniswap v3 DEX liquidity, pools, and optional tick distribution from The Graph.",
                OnchainDEXLiquidityInput,
            )
            add_tool(
                "onchain_governance",
                "DAO governance proposals from Snapshot (off-chain) and Tally (on-chain).",
                OnchainGovernanceInput,
            )
            add_tool(
                "onchain_token_unlocks",
                "Token vesting and unlock schedules from Token Unlocks.",
                OnchainTokenUnlocksInput,
            )
            add_tool(
                "onchain_activity",
                "Chain-level activity metrics (active addresses, tx count, gas usage) from Etherscan.",
                OnchainActivityInput,
            )
            add_tool(
                "onchain_contract_risk",
                "Smart contract risk analysis via GoPlus or Slither.",
                OnchainContractRiskInput,
            )
            add_tool(
                "crypto_news_search",
                "Search crypto news.",
                CryptoNewsSearchInput,
            )
            add_tool(
                "web_research_search",
                "Multi-source web and news search: Bing News, Brave Search, Kaito crypto news, and DuckDuckGo. Supports parallel search with configurable providers and result merging.",
                WebResearchInput,
            )
            add_tool(
                "macro_hub",
                "Macro economic and market indicators: Fear & Greed Index, FRED data (CPI, unemployment, GDP, rates), traditional indices (S&P500, NASDAQ, VIX), commodities (gold, oil), economic calendar, and CME FedWatch tool.",
                MacroHubInput,
            )
            add_tool(
                "grok_social_trace",
                "Trace the origin of a circulating message on X/Twitter using Grok, assess whether it is likely promotional, and provide deepsearch-based social analysis.",
                GrokSocialTraceInput,
            )
            add_tool(
                "etf_flows_holdings",
                "ETF flows and holdings data (free-first sources like Farside).",
                EtfFlowsHoldingsInput,
            )
            add_tool(
                "cex_netflow_reserves",
                "CEX reserves and optional whale transfer monitoring.",
                CexNetflowReservesInput,
            )
            add_tool(
                "lending_liquidation_risk",
                "Lending yield snapshots with optional liquidation data.",
                LendingLiquidationRiskInput,
            )
            add_tool(
                "stablecoin_health",
                "Stablecoin supply and chain distribution snapshots.",
                StablecoinHealthInput,
            )
            add_tool(
                "options_vol_skew",
                "Options volatility/skew snapshots from Deribit/OKX/Binance.",
                OptionsVolSkewInput,
            )
            add_tool(
                "blockspace_mev",
                "Blockspace and MEV-Boost stats with gas oracle data.",
                BlockspaceMevInput,
            )
            add_tool(
                "hyperliquid_market",
                "Hyperliquid market data (funding, OI, orderbook, trades).",
                HyperliquidMarketInput,
            )
            # 新增工具
            add_tool(
                "price_history",
                "Historical K-line data with technical indicators (SMA, EMA, RSI, MACD, Bollinger, ATR), statistics (volatility, max drawdown, Sharpe ratio), and support/resistance levels.",
                PriceHistoryInput,
            )
            add_tool(
                "sector_peers",
                "Sector/peer comparison analysis: get tokens in the same category with market metrics, TVL, fees, and comparative valuation.",
                SectorPeersInput,
            )
            add_tool(
                "sentiment_aggregator",
                "Multi-source sentiment aggregation from Telegram, Twitter/X (Grok), and news. Returns weighted sentiment score, source breakdown, and signals.",
                SentimentAggregatorInput,
            )

            return tools

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[dict[str, Any]]:
            """处理工具调用"""
            try:
                if name == "crypto_overview":
                    # 验证输入
                    input_params = CryptoOverviewInput(**arguments)

                    # 执行工具
                    result = await crypto_overview_tool.execute(input_params)

                    # 返回结果
                    return [
                        {
                            "type": "text",
                            "text": result.model_dump_json(indent=2)
                        }
                    ]

                elif name == "market_microstructure":
                    # 验证输入
                    input_params = MarketMicrostructureInput(**arguments)

                    # 执行工具
                    result = await self.market_microstructure_tool.execute(input_params)

                    # 返回结果
                    return [
                        {
                            "type": "text",
                            "text": result.model_dump_json(indent=2)
                        }
                    ]

                elif name == "derivatives_hub":
                    input_params = DerivativesHubInput(**arguments)
                    result = await self.derivatives_hub_tool.execute(input_params)
                    return [{"type": "text", "text": result.model_dump_json(indent=2)}]

                elif name == "crypto_news_search":
                    input_params = CryptoNewsSearchInput(**arguments)
                    result = await self.crypto_news_search_tool.execute(input_params)
                    return [{"type": "text", "text": result.model_dump_json(indent=2)}]

                elif name == "web_research_search":
                    input_params = WebResearchInput(**arguments)
                    result = await self.web_research_tool.execute(input_params)
                    return [{"type": "text", "text": result.model_dump_json(indent=2)}]

                elif name == "macro_hub":
                    input_params = MacroHubInput(**arguments)
                    result = await self.macro_hub_tool.execute(input_params)
                    return [{"type": "text", "text": result.model_dump_json(indent=2)}]

                elif name == "onchain_tvl_fees":
                    input_params = OnchainTVLFeesInput(**arguments)
                    result = await self.onchain_tvl_fees_tool.execute(input_params)
                    return [{"type": "text", "text": result.model_dump_json(indent=2)}]

                elif name == "onchain_stablecoins_cex":
                    input_params = OnchainStablecoinsCEXInput(**arguments)
                    result = await self.onchain_stablecoins_cex_tool.execute(input_params)
                    return [{"type": "text", "text": result.model_dump_json(indent=2)}]

                elif name == "onchain_bridge_volumes":
                    input_params = OnchainBridgeVolumesInput(**arguments)
                    result = await self.onchain_bridge_volumes_tool.execute(input_params)
                    return [{"type": "text", "text": result.model_dump_json(indent=2)}]

                elif name == "onchain_dex_liquidity":
                    input_params = OnchainDEXLiquidityInput(**arguments)
                    result = await self.onchain_dex_liquidity_tool.execute(input_params)
                    return [{"type": "text", "text": result.model_dump_json(indent=2)}]

                elif name == "onchain_governance":
                    input_params = OnchainGovernanceInput(**arguments)
                    result = await self.onchain_governance_tool.execute(input_params)
                    return [{"type": "text", "text": result.model_dump_json(indent=2)}]

                elif name == "onchain_token_unlocks":
                    input_params = OnchainTokenUnlocksInput(**arguments)
                    result = await self.onchain_token_unlocks_tool.execute(input_params)
                    return [{"type": "text", "text": result.model_dump_json(indent=2)}]

                elif name == "onchain_activity":
                    input_params = OnchainActivityInput(**arguments)
                    result = await self.onchain_activity_tool.execute(input_params)
                    return [{"type": "text", "text": result.model_dump_json(indent=2)}]

                elif name == "onchain_contract_risk":
                    input_params = OnchainContractRiskInput(**arguments)
                    result = await self.onchain_contract_risk_tool.execute(input_params)
                    return [{"type": "text", "text": result.model_dump_json(indent=2)}]

                elif name == "etf_flows_holdings":
                    input_params = EtfFlowsHoldingsInput(**arguments)
                    result = await self.etf_flows_holdings_tool.execute(input_params)
                    return [{"type": "text", "text": result.model_dump_json(indent=2)}]

                elif name == "cex_netflow_reserves":
                    input_params = CexNetflowReservesInput(**arguments)
                    result = await self.cex_netflow_reserves_tool.execute(input_params)
                    return [{"type": "text", "text": result.model_dump_json(indent=2)}]

                elif name == "lending_liquidation_risk":
                    input_params = LendingLiquidationRiskInput(**arguments)
                    result = await self.lending_liquidation_risk_tool.execute(input_params)
                    return [{"type": "text", "text": result.model_dump_json(indent=2)}]

                elif name == "stablecoin_health":
                    input_params = StablecoinHealthInput(**arguments)
                    result = await self.stablecoin_health_tool.execute(input_params)
                    return [{"type": "text", "text": result.model_dump_json(indent=2)}]

                elif name == "options_vol_skew":
                    input_params = OptionsVolSkewInput(**arguments)
                    result = await self.options_vol_skew_tool.execute(input_params)
                    return [{"type": "text", "text": result.model_dump_json(indent=2)}]

                elif name == "blockspace_mev":
                    input_params = BlockspaceMevInput(**arguments)
                    result = await self.blockspace_mev_tool.execute(input_params)
                    return [{"type": "text", "text": result.model_dump_json(indent=2)}]

                elif name == "hyperliquid_market":
                    input_params = HyperliquidMarketInput(**arguments)
                    result = await self.hyperliquid_market_tool.execute(input_params)
                    return [{"type": "text", "text": result.model_dump_json(indent=2)}]

                elif name == "grok_social_trace":
                    if not config.is_tool_enabled("grok_social_trace"):
                        return [
                            {
                                "type": "text",
                                "text": "Tool grok_social_trace is disabled by configuration.",
                            }
                        ]

                    input_params = GrokSocialTraceInput(**arguments)
                    result = await self.grok_social_trace_tool.execute(input_params)
                    return [
                        {
                            "type": "text",
                            "text": result.model_dump_json(indent=2),
                        }
                    ]

                # 新增工具处理
                elif name == "price_history":
                    input_params = PriceHistoryInput(**arguments)
                    result = await self.price_history_tool.execute(input_params)
                    return [{"type": "text", "text": result.model_dump_json(indent=2)}]

                elif name == "sector_peers":
                    input_params = SectorPeersInput(**arguments)
                    result = await self.sector_peers_tool.execute(input_params)
                    return [{"type": "text", "text": result.model_dump_json(indent=2)}]

                elif name == "sentiment_aggregator":
                    input_params = SentimentAggregatorInput(**arguments)
                    result = await self.sentiment_aggregator_tool.execute(input_params)
                    return [{"type": "text", "text": result.model_dump_json(indent=2)}]

                else:
                    return [{"type": "text", "text": f"Unknown tool: {name}"}]

            except Exception as e:
                logger.error(f"Tool execution failed", tool=name, error=str(e))
                return [
                    {
                        "type": "text",
                        "text": f"Error: {str(e)}"
                    }
                ]

        logger.info("Tools registered successfully")

    async def cleanup(self):
        """清理资源"""
        logger.info("Cleaning up resources...")

        # 关闭所有数据源连接
        await registry.close_all()

        # 关闭Redis连接
        await cache_manager.close()

        logger.info("Cleanup completed")

    async def run(self):
        """运行服务器"""
        try:
            # 初始化
            await self.initialize()

            # 运行stdio服务器
            async with stdio_server() as (read_stream, write_stream):
                logger.info("MCP server running on stdio")
                await self.server.run(
                    read_stream,
                    write_stream,
                    self.server.create_initialization_options()
                )

        except Exception as e:
            logger.error(f"Server error", error=str(e))
            raise

        finally:
            await self.cleanup()


def handle_signal(signum, frame):
    """处理退出信号"""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


def main():
    """主入口"""
    # 设置日志
    log_level = config.settings.log_level
    setup_logging(log_level)

    logger.info(
        "Starting Hubrium MCP Server",
        environment=config.settings.environment,
        log_level=log_level,
    )

    # 注册信号处理
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # 创建并运行服务器
    server = MCPServer()

    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
