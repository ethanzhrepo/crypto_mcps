"""
MCP工具真实API集成测试

这些测试直接调用真实API，验证Hub工具端到端功能。
运行方式: make test-live 或 make test-live-free
"""
import pytest


# ==================== CryptoOverviewTool Tests ====================

@pytest.mark.live
@pytest.mark.live_free
class TestCryptoOverviewToolLive:
    """CryptoOverviewTool 真实API测试"""

    @pytest.mark.asyncio
    async def test_get_complete_overview_btc(self):
        """测试获取BTC完整概览"""
        from src.tools.crypto.overview import CryptoOverviewTool

        tool = CryptoOverviewTool()
        result = await tool.execute({"symbol": "BTC"})

        assert result.symbol == "BTC"
        assert result.data.basic.name is not None
        assert result.data.market.price > 0
        assert result.data.market.market_cap > 0
        assert result.data.market.total_volume_24h > 0
        assert result.data.market.price_change_24h is not None

    @pytest.mark.asyncio
    async def test_get_complete_overview_eth(self):
        """测试获取ETH完整概览"""
        from src.tools.crypto.overview import CryptoOverviewTool

        tool = CryptoOverviewTool()
        result = await tool.execute({"symbol": "ETH"})

        assert result.symbol == "ETH"
        assert result.data.market.price > 0

    @pytest.mark.asyncio
    async def test_get_overview_with_metadata(self):
        """测试获取概览包含元数据"""
        from src.tools.crypto.overview import CryptoOverviewTool

        tool = CryptoOverviewTool()
        result = await tool.execute({"symbol": "BTC"})

        # 验证元数据
        assert hasattr(result, "source_meta")
        assert len(result.source_meta) > 0


# ==================== DerivativesHubTool Tests ====================

@pytest.mark.live
@pytest.mark.live_free
class TestDerivativesHubToolLive:
    """DerivativesHubTool 真实API测试（免费功能）"""

    @pytest.mark.asyncio
    async def test_funding_rates(self):
        """测试获取资金费率"""
        from src.tools.derivatives import DerivativesHubTool

        tool = DerivativesHubTool()
        result = await tool.execute({
            "symbol": "BTCUSDT",
            "feature": "funding_rates"
        })

        assert "data" in result or hasattr(result, "data")

    @pytest.mark.asyncio
    async def test_open_interest(self):
        """测试获取持仓量"""
        from src.tools.derivatives import DerivativesHubTool

        tool = DerivativesHubTool()
        result = await tool.execute({
            "symbol": "BTCUSDT",
            "feature": "open_interest"
        })

        assert result is not None

    @pytest.mark.asyncio
    async def test_long_short_ratio(self):
        """测试获取多空比"""
        from src.tools.derivatives import DerivativesHubTool

        tool = DerivativesHubTool()
        result = await tool.execute({
            "symbol": "BTCUSDT",
            "feature": "long_short_ratio"
        })

        assert result is not None

    @pytest.mark.asyncio
    async def test_options_chain(self):
        """测试获取期权链"""
        from src.tools.derivatives import DerivativesHubTool

        tool = DerivativesHubTool()
        result = await tool.execute({
            "symbol": "BTC",
            "feature": "options_chain"
        })

        assert result is not None

    @pytest.mark.asyncio
    async def test_volatility(self):
        """测试获取波动率"""
        from src.tools.derivatives import DerivativesHubTool

        tool = DerivativesHubTool()
        result = await tool.execute({
            "symbol": "BTC",
            "feature": "volatility"
        })

        assert result is not None


@pytest.mark.live
@pytest.mark.requires_key
class TestDerivativesHubToolLiveWithKey:
    """DerivativesHubTool 需要API密钥的测试"""

    @pytest.mark.asyncio
    async def test_liquidations(self, skip_if_no_key):
        """测试获取清算数据"""
        skip_if_no_key("COINGLASS_API_KEY")

        from src.tools.derivatives import DerivativesHubTool

        tool = DerivativesHubTool()
        result = await tool.execute({
            "symbol": "BTC",
            "feature": "liquidations"
        })

        assert result is not None

    @pytest.mark.asyncio
    async def test_borrow_rates(self, skip_if_no_key):
        """测试获取借贷利率"""
        skip_if_no_key("COINGLASS_API_KEY")

        from src.tools.derivatives import DerivativesHubTool

        tool = DerivativesHubTool()
        result = await tool.execute({
            "symbol": "BTC",
            "feature": "borrow_rates"
        })

        assert result is not None


 # （原 onchain_hub 已拆分为多个专用 onchain_* 工具，live 测试将在新工具稳定后单独补充）


# ==================== MacroHubTool Tests ====================

@pytest.mark.live
@pytest.mark.requires_key
class TestMacroHubToolLive:
    """MacroHubTool 真实API测试"""

    @pytest.mark.asyncio
    async def test_fred_data(self, skip_if_no_key):
        """测试获取FRED宏观数据"""
        skip_if_no_key("FRED_API_KEY")

        from src.tools.macro import MacroHubTool

        tool = MacroHubTool()
        result = await tool.execute({
            "indicator": "GDP",
            "feature": "economic_indicator"
        })

        assert result is not None

    @pytest.mark.asyncio
    async def test_interest_rates(self, skip_if_no_key):
        """测试获取利率数据"""
        skip_if_no_key("FRED_API_KEY")

        from src.tools.macro import MacroHubTool

        tool = MacroHubTool()
        result = await tool.execute({
            "feature": "interest_rates"
        })

        assert result is not None


# ==================== MarketMicrostructureTool Tests ====================

@pytest.mark.live
@pytest.mark.live_free
class TestMarketMicrostructureToolLive:
    """MarketMicrostructureTool 真实API测试"""

    @pytest.mark.asyncio
    async def test_orderbook(self):
        """测试获取订单簿"""
        from src.tools.market import MarketMicrostructureTool

        tool = MarketMicrostructureTool()
        result = await tool.execute({
            "symbol": "BTCUSDT",
            "feature": "orderbook"
        })

        assert result is not None

    @pytest.mark.asyncio
    async def test_klines(self):
        """测试获取K线数据"""
        from src.tools.market import MarketMicrostructureTool

        tool = MarketMicrostructureTool()
        result = await tool.execute({
            "symbol": "BTCUSDT",
            "interval": "1h",
            "feature": "klines"
        })

        assert result is not None

    @pytest.mark.asyncio
    async def test_ticker(self):
        """测试获取行情数据"""
        from src.tools.market import MarketMicrostructureTool

        tool = MarketMicrostructureTool()
        result = await tool.execute({
            "symbol": "BTCUSDT",
            "feature": "ticker"
        })

        assert result is not None


# ==================== WebSearchTool Tests ====================

@pytest.mark.live
@pytest.mark.requires_key
class TestWebSearchToolLive:
    """WebSearchTool 真实API测试"""

    @pytest.mark.asyncio
    async def test_google_search(self, skip_if_no_key):
        """测试Google搜索"""
        skip_if_no_key("GOOGLE_SEARCH_API_KEY")

        from src.tools.web_research import WebResearchTool

        tool = WebResearchTool()
        result = await tool.execute({
            "query": "Bitcoin price",
            "engine": "google",
            "limit": 5
        })

        assert result is not None

    @pytest.mark.asyncio
    async def test_brave_search(self, skip_if_no_key):
        """测试Brave搜索"""
        skip_if_no_key("BRAVE_SEARCH_API_KEY")

        from src.tools.web_research import WebResearchTool

        tool = WebResearchTool()
        result = await tool.execute({
            "query": "Ethereum news",
            "engine": "brave",
            "limit": 5
        })

        assert result is not None


# ==================== ContractAnalysisTool Tests ====================

@pytest.mark.live
@pytest.mark.live_free
class TestContractAnalysisToolLive:
    """ContractAnalysisTool 真实API测试"""

    @pytest.mark.asyncio
    async def test_contract_security_check(self):
        """测试合约安全检查"""
        from src.tools.contract_analysis import ContractAnalysisTool

        tool = ContractAnalysisTool()
        # USDT合约
        result = await tool.execute({
            "contract_address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
            "chain": "ethereum"
        })

        assert result is not None

    @pytest.mark.asyncio
    async def test_contract_security_weth(self):
        """测试WETH合约安全检查"""
        from src.tools.contract_analysis import ContractAnalysisTool

        tool = ContractAnalysisTool()
        result = await tool.execute({
            "contract_address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            "chain": "ethereum"
        })

        assert result is not None


# ==================== DeFiLlama Coins/Prices Tests ====================

@pytest.mark.live
@pytest.mark.live_free
class TestDefiLlamaPricesLive:
    """DeFiLlama Coins/Prices API 真实测试（合约地址查询）"""

    @pytest.mark.asyncio
    async def test_current_prices_usdc(self):
        """测试获取USDC当前价格（通过合约地址）"""
        from src.data_sources.defillama import DefiLlamaClient

        client = DefiLlamaClient()
        # USDC on Ethereum
        data, meta = await client.get_current_prices(
            coins="ethereum:0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
        )

        assert "coins" in data
        coin_data = data["coins"]["ethereum:0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"]
        assert coin_data["symbol"] == "USDC"
        assert coin_data["decimals"] == 6
        assert 0.9 < coin_data["price"] < 1.1  # USDC should be ~$1
        assert coin_data["confidence"] > 0.9
        assert meta.provider == "defillama"

    @pytest.mark.asyncio
    async def test_current_prices_multiple(self):
        """测试批量获取多个代币价格"""
        from src.data_sources.defillama import DefiLlamaClient

        client = DefiLlamaClient()
        # USDC and USDT on Ethereum
        data, meta = await client.get_current_prices(
            coins="ethereum:0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48,ethereum:0xdAC17F958D2ee523a2206206994597C13D831ec7"
        )

        assert "coins" in data
        assert len(data["coins"]) == 2
        assert "ethereum:0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48" in data["coins"]
        assert "ethereum:0xdAC17F958D2ee523a2206206994597C13D831ec7" in data["coins"]

    @pytest.mark.asyncio
    async def test_price_chart_usdc(self):
        """测试获取USDC价格图表"""
        from src.data_sources.defillama import DefiLlamaClient

        client = DefiLlamaClient()
        data, meta = await client.get_price_chart(
            coins="ethereum:0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            period="7d",
            span=24
        )

        assert "coins" in data
        coin_data = data["coins"]["ethereum:0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"]
        assert "prices" in coin_data
        assert len(coin_data["prices"]) > 0
        assert coin_data["symbol"] == "USDC"

    @pytest.mark.asyncio
    async def test_first_price_usdc(self):
        """测试获取USDC首次记录价格"""
        from src.data_sources.defillama import DefiLlamaClient

        client = DefiLlamaClient()
        data, meta = await client.get_first_price(
            coins="ethereum:0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
        )

        assert "coins" in data
        coin_data = data["coins"]["ethereum:0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"]
        assert "price" in coin_data
        assert "timestamp" in coin_data
        assert coin_data["symbol"] == "USDC"

    @pytest.mark.asyncio
    async def test_block_at_timestamp(self):
        """测试获取指定时间戳的区块高度"""
        from src.data_sources.defillama import DefiLlamaClient
        import time

        client = DefiLlamaClient()
        # Use a timestamp from 1 day ago
        timestamp = int(time.time()) - 86400
        data, meta = await client.get_block_at_timestamp(
            chain="ethereum",
            timestamp=timestamp
        )

        assert "height" in data
        assert "timestamp" in data
        assert data["height"] > 0
        assert meta.provider == "defillama"
