"""
数据源客户端真实API集成测试

这些测试直接调用真实API，用于验证客户端功能正确性。
运行方式: make test-live 或 make test-live-free
"""
import pytest


# ==================== CoinGecko Tests (FREE) ====================

@pytest.mark.live
@pytest.mark.live_free
class TestCoinGeckoLive:
    """CoinGecko API真实测试（免费API）"""

    @pytest.mark.asyncio
    async def test_get_coin_data_bitcoin(self):
        """测试获取BTC完整数据"""
        from src.data_sources.coingecko import CoinGeckoClient

        client = CoinGeckoClient()
        data = await client.get_coin_data("BTC")

        assert data["id"] == "bitcoin"
        assert data["symbol"] == "btc"
        assert "market_data" in data
        assert data["market_data"]["current_price"]["usd"] > 0

    @pytest.mark.asyncio
    async def test_get_coin_data_ethereum(self):
        """测试获取ETH数据"""
        from src.data_sources.coingecko import CoinGeckoClient

        client = CoinGeckoClient()
        data = await client.get_coin_data("ETH")

        assert data["id"] == "ethereum"
        assert "market_data" in data

    @pytest.mark.asyncio
    async def test_get_categories(self):
        """测试获取分类列表"""
        from src.data_sources.coingecko import CoinGeckoClient

        client = CoinGeckoClient()
        data, meta = await client.get_categories()

        assert isinstance(data, list)
        assert len(data) > 0
        assert meta.provider == "coingecko"


# ==================== DefiLlama Tests (FREE) ====================

@pytest.mark.live
@pytest.mark.live_free
class TestDefiLlamaLive:
    """DefiLlama API真实测试（免费API）"""

    @pytest.mark.asyncio
    async def test_get_protocol_tvl(self):
        """测试获取协议TVL"""
        from src.data_sources.defillama import DefiLlamaClient

        client = DefiLlamaClient()
        data, meta = await client.get_protocol_tvl("uniswap")

        assert "tvl" in data or "tvl_usd" in data
        assert meta.provider == "defillama"

    @pytest.mark.asyncio
    async def test_get_protocol_fees(self):
        """测试获取协议费用"""
        from src.data_sources.defillama import DefiLlamaClient

        client = DefiLlamaClient()
        data, meta = await client.get_protocol_fees("uniswap")

        assert isinstance(data, dict)


# ==================== DefiLlama Tests (PRO - Requires API Key) ====================

@pytest.mark.live
class TestDefiLlamaProLive:
    """DefiLlama API真实测试（需要Pro API Key）"""

    @pytest.mark.asyncio
    async def test_get_stablecoins(self):
        """测试获取稳定币数据"""
        from src.data_sources.defillama import DefiLlamaClient

        client = DefiLlamaClient()
        data, meta = await client.get_stablecoins()

        assert isinstance(data, (list, dict))

    @pytest.mark.asyncio
    async def test_get_bridge_volumes(self):
        """测试获取跨链桥数据"""
        from src.data_sources.defillama import DefiLlamaClient

        client = DefiLlamaClient()
        data, meta = await client.get_bridge_volumes()

        assert isinstance(data, (list, dict))

    @pytest.mark.asyncio
    async def test_get_yields(self):
        """测试获取收益率数据"""
        from src.data_sources.defillama import DefiLlamaClient

        client = DefiLlamaClient()
        data, meta = await client.get_yields()

        assert isinstance(data, list)


# ==================== Binance Tests (FREE) ====================

@pytest.mark.live
@pytest.mark.live_free
class TestBinanceLive:
    """Binance API真实测试（免费API）"""

    @pytest.mark.asyncio
    async def test_get_ticker(self):
        """测试获取24h行情"""
        from src.data_sources.binance import BinanceClient

        client = BinanceClient()
        data, meta = await client.get_ticker("BTCUSDT")

        assert data["symbol"] == "BTCUSDT"
        assert data["last_price"] > 0
        assert "volume_24h" in data

    @pytest.mark.asyncio
    async def test_get_klines(self):
        """测试获取K线数据"""
        from src.data_sources.binance import BinanceClient

        client = BinanceClient()
        data, meta = await client.get_klines("BTCUSDT", interval="1h", limit=10)

        assert isinstance(data, list)
        assert len(data) <= 10
        assert data[0]["open"] > 0

    @pytest.mark.asyncio
    async def test_get_orderbook(self):
        """测试获取订单簿"""
        from src.data_sources.binance import BinanceClient

        client = BinanceClient()
        data, meta = await client.get_orderbook("BTCUSDT", limit=10)

        assert "bids" in data
        assert "asks" in data
        assert len(data["bids"]) > 0

    @pytest.mark.asyncio
    async def test_get_funding_rate(self):
        """测试获取资金费率"""
        from src.data_sources.binance import BinanceClient

        client = BinanceClient()
        data, meta = await client.get_funding_rate("BTCUSDT")

        assert data["symbol"] == "BTCUSDT"
        assert "funding_rate" in data

    @pytest.mark.asyncio
    async def test_get_open_interest(self):
        """测试获取持仓量"""
        from src.data_sources.binance import BinanceClient

        client = BinanceClient()
        data, meta = await client.get_open_interest("BTCUSDT")

        assert data["symbol"] == "BTCUSDT"
        assert data["open_interest"] > 0

    @pytest.mark.asyncio
    async def test_get_long_short_ratio(self):
        """测试获取多空比"""
        from src.data_sources.binance import BinanceClient

        client = BinanceClient()
        data, meta = await client.get_long_short_ratio("BTCUSDT")

        assert isinstance(data, list)
        if len(data) > 0:
            assert "long_ratio" in data[0]


# ==================== Deribit Tests (FREE) ====================

@pytest.mark.live
@pytest.mark.live_free
class TestDeribitLive:
    """Deribit API真实测试（免费API）"""

    @pytest.mark.asyncio
    async def test_get_instruments(self):
        """测试获取期权合约列表"""
        from src.data_sources.deribit import DeribitClient

        client = DeribitClient()
        data, meta = await client.get_instruments(currency="BTC", kind="option")

        assert isinstance(data, list)
        assert len(data) > 0
        assert data[0]["kind"] == "option"

    @pytest.mark.asyncio
    async def test_get_volatility_index(self):
        """测试获取波动率指数"""
        from src.data_sources.deribit import DeribitClient

        client = DeribitClient()
        data, meta = await client.get_volatility_index(currency="BTC")

        assert data["currency"] == "BTC"
        assert "dvol" in data

    @pytest.mark.asyncio
    async def test_get_historical_volatility(self):
        """测试获取历史波动率"""
        from src.data_sources.deribit import DeribitClient

        client = DeribitClient()
        data, meta = await client.get_historical_volatility(currency="BTC")

        assert "data" in data


# ==================== Snapshot Tests (FREE) ====================

@pytest.mark.live
@pytest.mark.live_free
class TestSnapshotLive:
    """Snapshot API真实测试（免费API）"""

    @pytest.mark.asyncio
    async def test_get_proposals(self):
        """测试获取治理提案"""
        from src.data_sources.snapshot import SnapshotClient

        client = SnapshotClient()
        # 正确的Uniswap治理空间ID
        data, meta = await client.get_proposals("uniswapgovernance.eth", limit=5)

        assert data.dao is not None
        assert data.total_proposals >= 0
        assert meta.provider == "snapshot"

    @pytest.mark.asyncio
    async def test_get_space_info(self):
        """测试获取空间信息"""
        from src.data_sources.snapshot import SnapshotClient

        client = SnapshotClient()
        # 正确的Uniswap治理空间ID
        data, meta = await client.get_space_info("uniswapgovernance.eth")

        assert data.get("name") is not None

    @pytest.mark.asyncio
    async def test_health_check(self):
        """测试健康检查"""
        from src.data_sources.snapshot import SnapshotClient

        client = SnapshotClient()
        result = await client.health_check()

        assert result is True


# ==================== GoPlus Tests (FREE) ====================

@pytest.mark.live
@pytest.mark.live_free
class TestGoPlusLive:
    """GoPlus API真实测试（免费API）"""

    @pytest.mark.asyncio
    async def test_get_token_security(self):
        """测试获取代币安全信息 - WETH"""
        from src.data_sources.goplus import GoPlusClient

        client = GoPlusClient()
        # 使用WETH合约地址
        data, meta = await client.get_token_security(
            "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            "ethereum"
        )

        assert data.contract_address is not None
        assert data.provider == "goplus"
        assert data.risk_level in ["low", "medium", "high", "critical", "unknown"]

    @pytest.mark.asyncio
    async def test_get_token_security_usdt(self):
        """测试获取USDT安全信息"""
        from src.data_sources.goplus import GoPlusClient

        client = GoPlusClient()
        # USDT合约地址
        data, meta = await client.get_token_security(
            "0xdAC17F958D2ee523a2206206994597C13D831ec7",
            "ethereum"
        )

        assert data.risk_score is not None

    @pytest.mark.asyncio
    async def test_health_check(self):
        """测试健康检查"""
        from src.data_sources.goplus import GoPlusClient

        client = GoPlusClient()
        result = await client.health_check()

        assert result is True


# ==================== CoinMarketCap Tests (Requires Key) ====================

@pytest.mark.live
@pytest.mark.requires_key
class TestCoinMarketCapLive:
    """CoinMarketCap API真实测试（需要API密钥）"""

    @pytest.mark.asyncio
    async def test_get_quotes(self, skip_if_no_key):
        """测试获取报价数据"""
        skip_if_no_key("COINMARKETCAP_API_KEY")

        from src.data_sources.coinmarketcap import CoinMarketCapClient
        import os

        client = CoinMarketCapClient(api_key=os.getenv("COINMARKETCAP_API_KEY"))
        data, meta = await client.get_quotes("BTC")

        assert "BTC" in data
        assert data["BTC"]["quote"]["USD"]["price"] > 0


# ==================== Etherscan Tests (Requires Key) ====================

@pytest.mark.live
@pytest.mark.requires_key
class TestEtherscanLive:
    """Etherscan API真实测试（需要API密钥）"""

    @pytest.mark.asyncio
    async def test_get_chain_stats(self, skip_if_no_key):
        """测试获取链上统计"""
        skip_if_no_key("ETHERSCAN_API_KEY")

        from src.data_sources.etherscan import EtherscanClient
        import os

        client = EtherscanClient(
            chain="ethereum",
            api_key=os.getenv("ETHERSCAN_API_KEY")
        )
        data, meta = await client.get_chain_stats()

        assert data.chain == "ethereum"


# ==================== Coinglass Tests (Requires Key) ====================

@pytest.mark.live
@pytest.mark.requires_key
class TestCoinglassLive:
    """Coinglass API真实测试（需要API密钥）"""

    @pytest.mark.asyncio
    async def test_get_liquidation_aggregated(self, skip_if_no_key):
        """测试获取聚合清算数据"""
        skip_if_no_key("COINGLASS_API_KEY")

        from src.data_sources.coinglass import CoinglassClient
        import os

        client = CoinglassClient(api_key=os.getenv("COINGLASS_API_KEY"))
        data, meta = await client.get_liquidation_aggregated("BTC", lookback_hours=24)

        assert data.symbol == "BTC"


# ==================== Tally Tests (Requires Key) ====================

@pytest.mark.live
@pytest.mark.requires_key
class TestTallyLive:
    """Tally API真实测试（需要API密钥）"""

    @pytest.mark.asyncio
    async def test_get_proposals(self, skip_if_no_key):
        """测试获取链上治理提案"""
        skip_if_no_key("TALLY_API_KEY")

        from src.data_sources.tally import TallyClient
        import os

        client = TallyClient(api_key=os.getenv("TALLY_API_KEY"))
        # Compound Governor
        data, meta = await client.get_proposals(
            "0xc0Da02939E1441F497fd74F78cE7Decb17B66529",
            chain_id="eip155:1",
            limit=5
        )

        assert data.dao is not None


# ==================== Yahoo Finance Tests (FREE) ====================

@pytest.mark.live
@pytest.mark.live_free
class TestYahooFinanceLive:
    """Yahoo Finance API真实测试（免费API）"""

    @pytest.mark.asyncio
    async def test_get_quote_sp500(self):
        """测试获取S&P 500报价"""
        from src.data_sources.yfinance import YahooFinanceClient

        client = YahooFinanceClient()
        data, meta = await client.get_quote("^GSPC")

        assert data is not None
        assert data.get("symbol") == "^GSPC"
        assert data.get("price") is not None
        assert data["price"] > 0
        assert meta.provider == "yfinance"

    @pytest.mark.asyncio
    async def test_get_quote_bitcoin(self):
        """测试获取BTC-USD报价"""
        from src.data_sources.yfinance import YahooFinanceClient

        client = YahooFinanceClient()
        data, meta = await client.get_quote("BTC-USD")

        assert data is not None
        assert data.get("price") is not None
        assert data["price"] > 0

    @pytest.mark.asyncio
    async def test_get_market_indices(self):
        """测试获取主要市场指数"""
        from src.data_sources.yfinance import YahooFinanceClient

        client = YahooFinanceClient()
        data, meta = await client.get_market_indices()

        assert data is not None
        assert "sp500" in data
        assert "nasdaq" in data
        assert "russell2000" in data  # 新增

        # 验证SP500数据
        sp500 = data["sp500"]
        assert sp500 is not None
        assert sp500.get("price") is not None
        assert sp500["price"] > 0

    @pytest.mark.asyncio
    async def test_get_commodities(self):
        """测试获取商品数据"""
        from src.data_sources.yfinance import YahooFinanceClient

        client = YahooFinanceClient()
        data, meta = await client.get_commodities()

        assert data is not None
        assert "gold" in data
        assert "crude_oil" in data

        # 验证黄金数据
        gold = data["gold"]
        if gold is not None:
            assert gold.get("price") is not None

    @pytest.mark.asyncio
    async def test_get_dollar_index(self):
        """测试获取美元指数"""
        from src.data_sources.yfinance import YahooFinanceClient

        client = YahooFinanceClient()
        data, meta = await client.get_dollar_index()

        assert data is not None
        assert data.get("price") is not None
        assert data["price"] > 0

    @pytest.mark.asyncio
    async def test_get_multiple_quotes(self):
        """测试批量获取报价"""
        from src.data_sources.yfinance import YahooFinanceClient

        client = YahooFinanceClient()
        symbols = ["^GSPC", "^IXIC", "^VIX"]
        data, meta = await client.get_multiple_quotes(symbols)

        assert data is not None
        assert isinstance(data, dict)
        assert len(data) >= 1  # 至少返回一个有效结果


# ==================== FRED Tests (Requires Key) ====================

@pytest.mark.live
@pytest.mark.requires_key
class TestFREDLive:
    """FRED API真实测试（需要API密钥）"""

    @pytest.mark.asyncio
    async def test_get_latest_value_fed_funds(self, skip_if_no_key):
        """测试获取联邦基金利率"""
        skip_if_no_key("FRED_API_KEY")

        from src.data_sources.fred import FREDClient
        import os

        client = FREDClient(api_key=os.getenv("FRED_API_KEY"))
        result = await client.get_latest_value("DFEDTARU")

        # 返回 (data_dict, SourceMeta) 元组
        assert result is not None
        data, meta = result
        assert "value" in data
        value = data["value"]
        assert isinstance(value, (int, float))
        # 联邦基金利率应该在0-10%之间
        assert 0 <= value <= 10
        assert meta.provider == "fred"

    @pytest.mark.asyncio
    async def test_get_latest_value_cpi(self, skip_if_no_key):
        """测试获取CPI"""
        skip_if_no_key("FRED_API_KEY")

        from src.data_sources.fred import FREDClient
        import os

        client = FREDClient(api_key=os.getenv("FRED_API_KEY"))
        result = await client.get_latest_value("CPIAUCSL")

        data, meta = result
        assert "value" in data
        assert isinstance(data["value"], (int, float))

    @pytest.mark.asyncio
    async def test_get_series_with_yoy(self, skip_if_no_key):
        """测试获取YoY数据"""
        skip_if_no_key("FRED_API_KEY")

        from src.data_sources.fred import FREDClient
        import os

        client = FREDClient(api_key=os.getenv("FRED_API_KEY"))
        result = await client.get_series_with_yoy("CPIAUCSL")

        # 返回格式可能是 (value, yoy, meta) 或 ((value, yoy), meta)
        assert result is not None
        if len(result) == 2:
            data, meta = result
            if isinstance(data, dict):
                assert "value" in data
            elif isinstance(data, tuple):
                value, yoy = data
                assert isinstance(value, (int, float))
                assert isinstance(yoy, (int, float))

    @pytest.mark.asyncio
    async def test_get_treasury_10y(self, skip_if_no_key):
        """测试获取10年期国债收益率"""
        skip_if_no_key("FRED_API_KEY")

        from src.data_sources.fred import FREDClient
        import os

        client = FREDClient(api_key=os.getenv("FRED_API_KEY"))
        result = await client.get_latest_value("DGS10")

        data, meta = result
        assert "value" in data
        value = data["value"]
        assert isinstance(value, (int, float))
        # 10年期国债收益率应该在0-15%之间
        assert 0 <= value <= 15

    @pytest.mark.asyncio
    async def test_get_unemployment_rate(self, skip_if_no_key):
        """测试获取失业率"""
        skip_if_no_key("FRED_API_KEY")

        from src.data_sources.fred import FREDClient
        import os

        client = FREDClient(api_key=os.getenv("FRED_API_KEY"))
        result = await client.get_latest_value("UNRATE")

        data, meta = result
        assert "value" in data
        value = data["value"]
        assert isinstance(value, (int, float))
        # 失业率应该在0-30%之间
        assert 0 <= value <= 30
