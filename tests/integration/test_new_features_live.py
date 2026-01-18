"""
新功能真实API集成测试

这些测试验证新实现的功能是否正确工作。
运行方式: make test-live 或 make test-live-free
"""
import pytest


# ==================== Coinglass Client Tests ====================

@pytest.mark.live
@pytest.mark.requires_key
class TestCoinglassClientLive:
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
        assert data.total_liquidations >= 0
        assert meta.provider == "coinglass"

    @pytest.mark.asyncio
    async def test_get_borrow_rates(self, skip_if_no_key):
        """测试获取借贷利率"""
        skip_if_no_key("COINGLASS_API_KEY")

        from src.data_sources.coinglass import CoinglassClient
        import os

        client = CoinglassClient(api_key=os.getenv("COINGLASS_API_KEY"))
        data, meta = await client.get_borrow_rates("BTC")

        assert data.symbol == "BTC"
        assert len(data.rates) >= 0

    @pytest.mark.asyncio
    async def test_get_open_interest_history(self, skip_if_no_key):
        """测试获取OI历史"""
        skip_if_no_key("COINGLASS_API_KEY")

        from src.data_sources.coinglass import CoinglassClient
        import os

        client = CoinglassClient(api_key=os.getenv("COINGLASS_API_KEY"))
        data, meta = await client.get_open_interest_history("BTC", interval="1h")

        assert isinstance(data, list) or hasattr(data, "__iter__")


# ==================== TokenUnlocks Client Tests ====================

@pytest.mark.live
@pytest.mark.requires_key
class TestTokenUnlocksClientLive:
    """TokenUnlocks API真实测试（需要API密钥）"""

    @pytest.mark.asyncio
    async def test_get_unlock_schedule(self, skip_if_no_key):
        """测试获取解锁计划"""
        skip_if_no_key("TOKEN_UNLOCKS_API_KEY")

        from src.data_sources.token_unlocks import TokenUnlocksClient
        import os

        client = TokenUnlocksClient(api_key=os.getenv("TOKEN_UNLOCKS_API_KEY"))
        data, meta = await client.get_unlock_schedule("ARB")

        assert data.symbol == "ARB"
        assert meta.provider == "token_unlocks"

    @pytest.mark.asyncio
    async def test_get_upcoming_unlocks(self, skip_if_no_key):
        """测试获取即将解锁"""
        skip_if_no_key("TOKEN_UNLOCKS_API_KEY")

        from src.data_sources.token_unlocks import TokenUnlocksClient
        import os

        client = TokenUnlocksClient(api_key=os.getenv("TOKEN_UNLOCKS_API_KEY"))
        data, meta = await client.get_upcoming_unlocks(days=30)

        assert isinstance(data, list) or hasattr(data, "unlocks")


# ==================== Tally Client Tests ====================

@pytest.mark.live
@pytest.mark.requires_key
class TestTallyClientLive:
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
        assert meta.provider == "tally"

    @pytest.mark.asyncio
    async def test_get_governor_info(self, skip_if_no_key):
        """测试获取Governor信息"""
        skip_if_no_key("TALLY_API_KEY")

        from src.data_sources.tally import TallyClient
        import os

        client = TallyClient(api_key=os.getenv("TALLY_API_KEY"))
        data, meta = await client.get_governor_info(
            "0xc0Da02939E1441F497fd74F78cE7Decb17B66529",
            chain_id="eip155:1"
        )

        assert data is not None


# ==================== Governance Feature Tests ====================

@pytest.mark.live
@pytest.mark.live_free
class TestGovernanceFeaturesLive:
    """治理功能真实测试"""

    @pytest.mark.asyncio
    async def test_snapshot_governance_uniswap(self):
        """测试Snapshot治理 - Uniswap"""
        from src.data_sources.snapshot import SnapshotClient

        client = SnapshotClient()
        data, meta = await client.get_proposals("uniswap.eth", limit=5)

        assert data.dao is not None
        assert data.total_proposals >= 0

    @pytest.mark.asyncio
    async def test_snapshot_governance_aave(self):
        """测试Snapshot治理 - Aave"""
        from src.data_sources.snapshot import SnapshotClient

        client = SnapshotClient()
        data, meta = await client.get_proposals("aave.eth", limit=5)

        assert data.dao is not None

    @pytest.mark.asyncio
    async def test_snapshot_voting_power(self):
        """测试获取投票权"""
        from src.data_sources.snapshot import SnapshotClient

        client = SnapshotClient()
        # 使用知名地址测试
        data, meta = await client.get_voting_power(
            "uniswap.eth",
            "0x0000000000000000000000000000000000000000"
        )

        assert data is not None


# ==================== Contract Risk Analysis Tests ====================

@pytest.mark.live
@pytest.mark.live_free
class TestContractRiskAnalysisLive:
    """合约风险分析真实测试"""

    @pytest.mark.asyncio
    async def test_goplus_weth(self):
        """测试GoPlus分析WETH"""
        from src.data_sources.goplus import GoPlusClient

        client = GoPlusClient()
        data, meta = await client.get_token_security(
            "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            "ethereum"
        )

        assert data.contract_address is not None
        assert data.risk_level in ["low", "medium", "high", "critical", "unknown"]

    @pytest.mark.asyncio
    async def test_goplus_usdc(self):
        """测试GoPlus分析USDC"""
        from src.data_sources.goplus import GoPlusClient

        client = GoPlusClient()
        # USDC合约
        data, meta = await client.get_token_security(
            "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "ethereum"
        )

        assert data.risk_score is not None

    @pytest.mark.asyncio
    async def test_goplus_bsc_token(self):
        """测试GoPlus分析BSC代币"""
        from src.data_sources.goplus import GoPlusClient

        client = GoPlusClient()
        # BUSD合约
        data, meta = await client.get_token_security(
            "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
            "bsc"
        )

        assert data.contract_address is not None


# ==================== Options & Derivatives Tests ====================

@pytest.mark.live
@pytest.mark.live_free
class TestOptionsDerivativesLive:
    """期权和衍生品真实测试"""

    @pytest.mark.asyncio
    async def test_deribit_btc_options(self):
        """测试Deribit BTC期权"""
        from src.data_sources.deribit import DeribitClient

        client = DeribitClient()
        data, meta = await client.get_instruments(
            currency="BTC",
            kind="option"
        )

        assert isinstance(data, list)
        assert len(data) > 0
        for instrument in data[:5]:  # 检查前5个
            assert instrument["kind"] == "option"

    @pytest.mark.asyncio
    async def test_deribit_eth_options(self):
        """测试Deribit ETH期权"""
        from src.data_sources.deribit import DeribitClient

        client = DeribitClient()
        data, meta = await client.get_instruments(
            currency="ETH",
            kind="option"
        )

        assert isinstance(data, list)
        assert len(data) > 0

    @pytest.mark.asyncio
    async def test_deribit_perpetual(self):
        """测试Deribit永续合约"""
        from src.data_sources.deribit import DeribitClient

        client = DeribitClient()
        data, meta = await client.get_instruments(
            currency="BTC",
            kind="future"
        )

        assert isinstance(data, list)
        # 应该包含永续合约
        perpetuals = [d for d in data if "PERPETUAL" in d.get("instrument_name", "")]
        assert len(perpetuals) > 0


# ==================== DeFi Protocol Tests ====================

@pytest.mark.live
@pytest.mark.live_free
class TestDeFiProtocolsLive:
    """DeFi协议真实测试"""

    @pytest.mark.asyncio
    async def test_defillama_uniswap(self):
        """测试DefiLlama - Uniswap"""
        from src.data_sources.defillama import DefiLlamaClient

        client = DefiLlamaClient()
        data, meta = await client.get_protocol_tvl("uniswap")

        assert "tvl" in data or "tvl_usd" in data

    @pytest.mark.asyncio
    async def test_defillama_aave(self):
        """测试DefiLlama - Aave"""
        from src.data_sources.defillama import DefiLlamaClient

        client = DefiLlamaClient()
        data, meta = await client.get_protocol_tvl("aave")

        assert "tvl" in data or "tvl_usd" in data

    @pytest.mark.asyncio
    async def test_defillama_chain_tvl(self):
        """测试DefiLlama链TVL"""
        from src.data_sources.defillama import DefiLlamaClient

        client = DefiLlamaClient()
        data, meta = await client.get_chain_tvl("ethereum")

        assert data is not None

    @pytest.mark.asyncio
    async def test_defillama_dex_volume(self):
        """测试DefiLlama DEX交易量"""
        from src.data_sources.defillama import DefiLlamaClient

        client = DefiLlamaClient()
        data, meta = await client.get_dex_volumes()

        assert isinstance(data, (list, dict))


# ==================== End-to-End Feature Tests ====================

@pytest.mark.live
@pytest.mark.live_free
class TestEndToEndFeaturesLive:
    """端到端功能测试"""

    @pytest.mark.asyncio
    async def test_complete_derivatives_analysis(self):
        """测试完整衍生品分析流程"""
        from src.data_sources.binance import BinanceClient
        from src.data_sources.deribit import DeribitClient

        # Binance期货数据
        binance = BinanceClient()
        funding, _ = await binance.get_funding_rate("BTCUSDT")
        oi, _ = await binance.get_open_interest("BTCUSDT")

        assert funding["symbol"] == "BTCUSDT"
        assert oi["open_interest"] > 0

        # Deribit期权数据
        deribit = DeribitClient()
        dvol, _ = await deribit.get_volatility_index("BTC")

        assert dvol["dvol"] > 0

    @pytest.mark.asyncio
    async def test_complete_onchain_analysis(self):
        """测试完整链上分析流程"""
        from src.data_sources.defillama import DefiLlamaClient
        from src.data_sources.goplus import GoPlusClient

        # TVL数据
        defillama = DefiLlamaClient()
        tvl, _ = await defillama.get_protocol_tvl("uniswap")

        assert "tvl" in tvl or "tvl_usd" in tvl

        # 合约安全
        goplus = GoPlusClient()
        security, _ = await goplus.get_token_security(
            "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            "ethereum"
        )

        assert security.risk_level is not None

    @pytest.mark.asyncio
    async def test_multi_exchange_comparison(self):
        """测试多交易所数据比较"""
        from src.data_sources.binance import BinanceClient
        from src.data_sources.coingecko import CoinGeckoClient

        # Binance价格
        binance = BinanceClient()
        ticker, _ = await binance.get_ticker("BTCUSDT")
        binance_price = ticker["last_price"]

        # CoinGecko价格
        coingecko = CoinGeckoClient()
        data = await coingecko.get_coin_data("BTC")
        cg_price = data["market_data"]["current_price"]["usd"]

        # 价格差异应在合理范围内 (1%)
        diff_pct = abs(binance_price - cg_price) / cg_price * 100
        assert diff_pct < 1, f"Price difference too large: {diff_pct}%"
