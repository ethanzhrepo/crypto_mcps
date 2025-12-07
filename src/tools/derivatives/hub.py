"""
derivatives_hub 工具实现

提供统一的衍生品数据入口：
- funding_rate: 资金费率
- open_interest: 未平仓量
- liquidations: 清算数据（暂不支持，Binance公开API无此数据）
- long_short_ratio: 多空比
- basis_curve: 基差曲线（需要现货+期货价格）
- term_structure: 期限结构（需要多个合约到期日）
- options_surface: 期权曲面（需要Deribit等期权数据源，暂不实现）
- options_metrics: 期权指标（暂不实现）
- borrow_rates: 借贷利率（暂不实现）
"""
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import structlog

from src.core.models import (
    BasisCurve,
    BasisPoint,
    BorrowRate,
    DerivativesHubData,
    DerivativesHubInput,
    DerivativesHubOutput,
    FundingRateData,
    LiquidationsData,
    LongShortRatioData,
    OpenInterestData,
    OptionsContract,
    OptionsMetrics,
    OptionsSurface,
    SourceMeta,
)
from src.data_sources.binance import BinanceClient
from src.data_sources.coinglass import CoinglassClient
from src.data_sources.defillama import DefiLlamaClient
from src.data_sources.deribit import DeribitClient
from src.data_sources.okx import OKXClient
from src.tools.derivatives.calculations import BasisCalculator

logger = structlog.get_logger()


class DerivativesHubTool:
    """derivatives_hub工具"""

    def __init__(
        self,
        binance_client: Optional[BinanceClient] = None,
        okx_client: Optional[OKXClient] = None,
        deribit_client: Optional[DeribitClient] = None,
        coinglass_client: Optional[CoinglassClient] = None,
        defillama_client: Optional[DefiLlamaClient] = None,
    ):
        """
        初始化derivatives_hub工具

        Args:
            binance_client: Binance客户端（可选，默认创建新实例）
            okx_client: OKX客户端（可选，用于fallback）
            deribit_client: Deribit客户端（可选，用于期权数据）
            coinglass_client: Coinglass客户端（可选，用于清算数据）
            defillama_client: DefiLlama客户端（可选，用于借贷利率）
        """
        self.binance = binance_client or BinanceClient()
        self.okx = okx_client  # Optional fallback source
        self.deribit = deribit_client  # Optional for options data
        self.coinglass = coinglass_client  # Optional for liquidation data
        self.defillama = defillama_client  # Optional for borrow rates
        self.basis_calculator = BasisCalculator()

        logger.info(
            "derivatives_hub_tool_initialized",
            has_binance=True,
            has_okx_fallback=okx_client is not None,
            has_deribit=deribit_client is not None,
            has_coinglass=coinglass_client is not None,
            has_defillama=defillama_client is not None,
        )

    async def execute(
        self, params
    ) -> DerivativesHubOutput:
        """
        执行derivatives_hub查询

        Args:
            params: 输入参数（可以是字典或DerivativesHubInput）

        Returns:
            DerivativesHubOutput
        """
        # 如果传入字典，转换为Pydantic模型
        if isinstance(params, dict):
            params = DerivativesHubInput(**params)

        start_time = time.time()
        logger.info(
            "derivatives_hub_execute_start",
            symbol=params.symbol,
            fields=params.include_fields,
        )

        # 标准化交易对符号
        symbol = self._normalize_symbol(params.symbol)

        # 收集数据
        data = DerivativesHubData()
        source_metas = []
        conflicts = []
        warnings = []

        # 根据include_fields获取数据
        if "all" in params.include_fields or "funding_rate" in params.include_fields:
            funding, meta = await self._fetch_funding_rate(symbol)
            data.funding_rate = funding
            source_metas.append(meta)

        if "all" in params.include_fields or "open_interest" in params.include_fields:
            oi, meta = await self._fetch_open_interest(symbol)
            data.open_interest = oi
            source_metas.append(meta)

        if "all" in params.include_fields or "long_short_ratio" in params.include_fields:
            lsr, meta = await self._fetch_long_short_ratio(symbol)
            data.long_short_ratio = lsr
            source_metas.append(meta)

        # 计算型字段
        if "all" in params.include_fields or "basis_curve" in params.include_fields:
            # 基差曲线需要现货价格和期货价格
            # 简化版：只计算永续合约的基差
            if data.funding_rate:
                basis_curve = self._calculate_basis_curve(symbol, data.funding_rate)
                data.basis_curve = basis_curve
            else:
                warnings.append("basis_curve requires funding_rate data")

        # 清算数据 (Coinglass)
        if "all" in params.include_fields or "liquidations" in params.include_fields:
            if self.coinglass:
                try:
                    liquidations, meta = await self._fetch_liquidations(
                        symbol, params.lookback_hours
                    )
                    data.liquidations = liquidations
                    source_metas.append(meta)
                except Exception as e:
                    logger.warning(f"Failed to fetch liquidations: {e}")
                    warnings.append(f"liquidations fetch failed: {str(e)}")
            else:
                warnings.append("liquidations requires Coinglass client (not configured)")

        if "all" in params.include_fields or "term_structure" in params.include_fields:
            try:
                term_structure, meta = await self._fetch_term_structure(symbol)
                data.term_structure = term_structure
                source_metas.append(meta)
            except Exception as e:
                logger.warning(f"Failed to fetch term_structure: {e}")
                warnings.append(f"term_structure fetch failed: {str(e)}")

        # 期权曲面（Deribit）
        if "all" in params.include_fields or "options_surface" in params.include_fields:
            if self.deribit:
                try:
                    options_surface, meta = await self._fetch_options_surface(
                        symbol=symbol,
                        expiry_date=params.options_expiry,
                    )
                    data.options_surface = options_surface
                    source_metas.append(meta)
                except Exception as e:
                    logger.warning(f"Failed to fetch options_surface: {e}")
                    warnings.append(f"options_surface fetch failed: {str(e)}")
            else:
                warnings.append("options_surface requires Deribit client (not configured)")

        # 期权市场指标（Deribit）
        if "all" in params.include_fields or "options_metrics" in params.include_fields:
            if self.deribit:
                try:
                    options_metrics, meta = await self._fetch_options_metrics(symbol)
                    data.options_metrics = options_metrics
                    source_metas.append(meta)
                except Exception as e:
                    logger.warning(f"Failed to fetch options_metrics: {e}")
                    warnings.append(f"options_metrics fetch failed: {str(e)}")
            else:
                warnings.append("options_metrics requires Deribit client (not configured)")

        # 借贷利率 (DefiLlama Yields)
        if "all" in params.include_fields or "borrow_rates" in params.include_fields:
            if self.defillama:
                try:
                    borrow_rates, meta = await self._fetch_borrow_rates(symbol)
                    data.borrow_rates = borrow_rates
                    source_metas.append(meta)
                except Exception as e:
                    logger.warning(f"Failed to fetch borrow_rates: {e}")
                    warnings.append(f"borrow_rates fetch failed: {str(e)}")
            else:
                warnings.append("borrow_rates requires DefiLlama client (not configured)")

        elapsed = time.time() - start_time
        logger.info(
            "derivatives_hub_execute_complete",
            symbol=symbol,
            elapsed_ms=round(elapsed * 1000, 2),
        )

        return DerivativesHubOutput(
            symbol=symbol,
            data=data,
            source_meta=source_metas,
            conflicts=conflicts,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )

    # ==================== 数据获取方法 ====================

    async def _fetch_funding_rate(
        self, symbol: str
    ) -> Tuple[FundingRateData, SourceMeta]:
        """获取资金费率（支持Binance和OKX，自动fallback）"""
        try:
            data, meta = await self.binance.get_funding_rate(symbol)
            return FundingRateData(**data), meta
        except Exception as e:
            if self.okx:
                logger.warning(
                    f"Binance funding rate failed, falling back to OKX: {e}",
                    symbol=symbol,
                )
                okx_symbol = self.okx.normalize_symbol(symbol, "swap")
                data, meta = await self.okx.get_funding_rate(okx_symbol)
                return FundingRateData(**data), meta
            raise

    async def _fetch_open_interest(
        self, symbol: str
    ) -> Tuple[OpenInterestData, SourceMeta]:
        """获取未平仓量（支持Binance和OKX，自动fallback）"""
        try:
            data, meta = await self.binance.get_open_interest(symbol)

            # 尝试获取标记价格来计算USD价值
            try:
                mark_data, _ = await self.binance.get_mark_price(symbol)
                mark_price = mark_data["mark_price"]
                data["open_interest_usd"] = data["open_interest"] * mark_price
            except:
                logger.warning("Failed to fetch mark price for OI USD calculation")
                data["open_interest_usd"] = 0

            return OpenInterestData(**data), meta
        except Exception as e:
            if self.okx:
                logger.warning(
                    f"Binance open interest failed, falling back to OKX: {e}",
                    symbol=symbol,
                )
                okx_symbol = self.okx.normalize_symbol(symbol, "swap")
                data, meta = await self.okx.get_open_interest(okx_symbol)

                # 尝试从OKX获取标记价格
                try:
                    mark_data, _ = await self.okx.get_mark_price(okx_symbol)
                    mark_price = mark_data["mark_price"]
                    data["open_interest_usd"] = data["open_interest"] * mark_price
                except:
                    logger.warning("Failed to fetch OKX mark price for OI USD calculation")
                    data["open_interest_usd"] = 0

                return OpenInterestData(**data), meta
            raise

    async def _fetch_long_short_ratio(
        self, symbol: str
    ) -> Tuple[List[LongShortRatioData], SourceMeta]:
        """获取多空比"""
        data, meta = await self.binance.get_long_short_ratio(symbol, period="1h")
        return [LongShortRatioData(**d) for d in data], meta

    async def _fetch_liquidations(
        self, symbol: str, lookback_hours: int
    ) -> Tuple[LiquidationsData, SourceMeta]:
        """
        获取清算数据（Coinglass）

        Args:
            symbol: 交易对
            lookback_hours: 回溯小时数

        Returns:
            (清算数据, SourceMeta)
        """
        # 从symbol提取币种 (BTCUSDT -> BTC)
        currency = self._extract_currency(symbol)

        liquidations_data, meta = await self.coinglass.get_liquidation_aggregated(
            symbol=currency,
            lookback_hours=lookback_hours,
        )
        return liquidations_data, meta

    async def _fetch_borrow_rates(
        self, symbol: str
    ) -> Tuple[List[BorrowRate], SourceMeta]:
        """
        获取借贷利率（DefiLlama）

        Args:
            symbol: 交易对

        Returns:
            (借贷利率列表, SourceMeta)
        """
        # 从symbol提取币种 (BTCUSDT -> BTC)
        currency = self._extract_currency(symbol)

        rates_data, meta = await self.defillama.get_borrow_rates(symbol=currency)

        # 转换为BorrowRate模型
        borrow_rates = []
        for rate in rates_data[:10]:  # 限制返回数量
            borrow_rates.append(BorrowRate(
                asset=rate.get("asset", currency),
                exchange=rate.get("exchange", "unknown"),
                hourly_rate=rate.get("hourly_rate", 0),
                daily_rate=rate.get("daily_rate", 0),
                annual_rate=rate.get("annual_rate", 0),
                available=rate.get("tvl_usd", 0),  # 使用TVL作为可用额度
                timestamp=rate.get("timestamp", datetime.utcnow().isoformat() + "Z"),
            ))

        return borrow_rates, meta

    async def _fetch_options_surface(
        self, symbol: str, expiry_date: Optional[str]
    ) -> Tuple[OptionsSurface, SourceMeta]:
        """
        获取期权曲面数据

        Args:
            symbol: 交易对（如BTCUSDT）
            expiry_date: 到期日（如30DEC24），可选

        Returns:
            (OptionsSurface, SourceMeta)
        """
        # 从symbol提取币种 (BTCUSDT -> BTC)
        currency = self._extract_currency(symbol)

        # 如果没有指定到期日，获取最近的到期日
        if not expiry_date:
            # 获取所有合约，找到最近的到期日
            instruments, _ = await self.deribit.get_instruments(currency=currency, kind="option")
            if not instruments:
                raise ValueError(f"No options found for {currency}")

            # 提取所有到期日
            expiry_dates = set()
            for inst in instruments:
                name = inst.get("instrument_name", "")
                # Deribit格式: BTC-30DEC24-100000-C
                parts = name.split("-")
                if len(parts) >= 2:
                    expiry_dates.add(parts[1])

            # 使用最近的到期日
            if expiry_dates:
                expiry_date = sorted(expiry_dates)[0]
            else:
                raise ValueError(f"No expiry dates found for {currency}")

        # 获取指定到期日的期权链
        options_chain, meta = await self.deribit.get_options_chain(
            currency=currency,
            expiry_date=expiry_date,
        )

        # 分离call和put
        calls = []
        puts = []

        for option in options_chain:
            # 获取每个期权的详细ticker数据（包含Greeks和IV）
            instrument_name = option.get("instrument_name")
            if not instrument_name:
                continue

            try:
                ticker, _ = await self.deribit.get_ticker(instrument_name)

                contract = OptionsContract(
                    strike=option.get("strike", 0),
                    option_type=option.get("option_type", ""),
                    expiry_date=expiry_date,
                    mark_price=ticker.get("mark_price", 0),
                    mark_iv=ticker.get("mark_iv", 0),
                    bid=ticker.get("best_bid_price"),
                    ask=ticker.get("best_ask_price"),
                    volume_24h=ticker.get("volume", 0),
                    open_interest=ticker.get("open_interest", 0),
                    delta=ticker.get("delta"),
                    gamma=ticker.get("gamma"),
                    theta=ticker.get("theta"),
                    vega=ticker.get("vega"),
                    rho=ticker.get("rho"),
                )

                if option.get("option_type") == "call":
                    calls.append(contract)
                else:
                    puts.append(contract)

            except Exception as e:
                logger.warning(f"Failed to fetch ticker for {instrument_name}: {e}")
                continue

        # 计算ATM IV和skew
        atm_iv, skew_25delta = self._calculate_iv_metrics(calls, puts)

        options_surface = OptionsSurface(
            currency=currency,
            exchange="deribit",
            expiry_date=expiry_date,
            atm_iv=atm_iv,
            skew_25delta=skew_25delta,
            calls=calls,
            puts=puts,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

        return options_surface, meta

    async def _fetch_options_metrics(
        self, symbol: str
    ) -> Tuple[OptionsMetrics, SourceMeta]:
        """
        获取期权市场指标

        Args:
            symbol: 交易对

        Returns:
            (OptionsMetrics, SourceMeta)
        """
        currency = self._extract_currency(symbol)

        # 获取波动率指数
        dvol_data, meta = await self.deribit.get_volatility_index(currency)
        dvol = dvol_data.get("dvol")

        # 获取所有未过期期权以计算指标
        instruments, _ = await self.deribit.get_instruments(currency=currency, kind="option")

        total_oi_usd = 0
        total_volume_24h_usd = 0
        call_oi = 0
        put_oi = 0

        for inst in instruments:
            instrument_name = inst.get("instrument_name")
            try:
                ticker, _ = await self.deribit.get_ticker(instrument_name)
                oi = ticker.get("open_interest", 0)
                volume_usd = ticker.get("volume_usd", 0)
                mark_price = ticker.get("mark_price", 0)

                total_oi_usd += oi * mark_price
                total_volume_24h_usd += volume_usd

                if inst.get("option_type") == "call":
                    call_oi += oi
                else:
                    put_oi += oi

            except Exception as e:
                logger.debug(f"Failed to fetch ticker for {instrument_name}: {e}")
                continue

        # 计算Put/Call比率
        put_call_ratio = put_oi / call_oi if call_oi > 0 else 0

        options_metrics = OptionsMetrics(
            currency=currency,
            exchange="deribit",
            dvol_index=dvol,
            put_call_ratio=put_call_ratio,
            total_oi_usd=total_oi_usd,
            total_volume_24h_usd=total_volume_24h_usd,
            iv_rank=None,  # 需要历史数据计算
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

        return options_metrics, meta

    async def _fetch_term_structure(
        self, symbol: str
    ) -> Tuple["TermStructure", SourceMeta]:
        """
        获取期限结构（futures term structure）

        Args:
            symbol: 交易对

        Returns:
            (TermStructure, SourceMeta)
        """
        from src.core.models import TermStructure, TermStructurePoint
        from datetime import datetime, timedelta

        # 获取现货价格（通过永续合约的index价格）
        mark_data, meta = await self.binance.get_mark_price(symbol)
        spot_price = float(mark_data.get("indexPrice", 0))
        current_time = datetime.utcnow()

        # 构建期限结构点列表
        points: List[TermStructurePoint] = []

        # 1. 永续合约（作为基准点）
        perp_price = float(mark_data.get("markPrice", 0))
        if perp_price > 0 and spot_price > 0:
            # 永续合约的隐含收益率基于资金费率
            funding_data, _ = await self._fetch_funding_rate(symbol)
            # 年化收益率 = 资金费率年化
            implied_yield_perp = funding_data.funding_rate_annual / 100  # 转换为小数

            points.append(TermStructurePoint(
                expiry_date="perpetual",
                days_to_expiry=0,
                implied_yield=implied_yield_perp,
                open_interest=0,  # 将在后续填充
                volume_24h=0,
            ))

        # 2. TODO: 添加季度合约数据
        # Binance交割合约格式: BTCUSDT_250328 (2025年3月28日到期)
        # 需要实现以下功能:
        # - 从Binance获取所有可用的交割合约列表
        # - 获取每个合约的价格、未平仓量、成交量
        # - 解析到期日并计算天数
        # - 计算隐含收益率: (future_price/spot_price - 1) * (365/days_to_expiry)
        #
        # 示例代码框架:
        # quarterly_contracts = await self._get_delivery_contracts(symbol)
        # for contract in quarterly_contracts:
        #     contract_symbol = contract["symbol"]  # e.g., BTCUSDT_250328
        #     expiry_date = self._parse_expiry_date(contract_symbol)
        #     days_to_expiry = (expiry_date - current_time).days
        #     contract_price = await self._get_contract_price(contract_symbol)
        #     implied_yield = (contract_price/spot_price - 1) * (365/days_to_expiry)
        #     points.append(TermStructurePoint(...))

        # 判断曲线形态
        slope = "flat"
        if len(points) >= 2:
            # 比较收益率曲线斜率
            first_yield = points[0].implied_yield
            last_yield = points[-1].implied_yield

            if last_yield > first_yield + 0.01:  # 1% 阈值
                slope = "normal"  # 正向曲线（远期高于近期）
            elif last_yield < first_yield - 0.01:
                slope = "inverted"  # 倒挂曲线（远期低于近期）

        term_structure = TermStructure(
            symbol=symbol,
            timestamp=datetime.utcnow().isoformat() + "Z",
            curve=points,
            slope=slope,
        )

        return term_structure, meta

    # ==================== 计算方法 ====================

    def _calculate_basis_curve(
        self, symbol: str, funding_data: FundingRateData
    ) -> BasisCurve:
        """
        计算基差曲线（简化版：只包含永续合约）

        Args:
            symbol: 交易对
            funding_data: 资金费率数据

        Returns:
            基差曲线
        """
        # 永续合约没有到期日，基差通过mark_price和index_price计算
        spot_price = funding_data.index_price or funding_data.mark_price
        future_price = funding_data.mark_price

        basis_result = self.basis_calculator.calculate_basis(spot_price, future_price)

        # 创建永续合约基差点
        perpetual_point = BasisPoint(
            contract_type="perpetual",
            expiry_date=None,
            days_to_expiry=None,
            spot_price=spot_price,
            future_price=future_price,
            basis_absolute=basis_result["basis_absolute"],
            basis_percent=basis_result["basis_percent"],
            basis_annualized=0,  # 永续合约无到期日，不计算年化
        )

        # 判断升水/贴水
        contango = basis_result["basis_absolute"] > 0

        return BasisCurve(
            symbol=symbol,
            timestamp=funding_data.timestamp,
            spot_price=spot_price,
            points=[perpetual_point],
            contango=contango,
        )

    # ==================== 辅助方法 ====================

    def _normalize_symbol(self, symbol: str) -> str:
        """
        标准化交易对符号为Binance格式

        Args:
            symbol: 输入符号，如 BTC/USDT, BTCUSDT

        Returns:
            标准化符号: BTCUSDT
        """
        # 移除斜杠
        symbol = symbol.replace("/", "").upper()

        # 如果不包含USDT后缀，添加之
        if not symbol.endswith("USDT"):
            symbol = symbol + "USDT"

        return symbol

    def _extract_currency(self, symbol: str) -> str:
        """
        从交易对提取币种

        Args:
            symbol: 交易对（如BTCUSDT）

        Returns:
            币种（如BTC）
        """
        symbol = symbol.replace("/", "").upper()

        # 常见计价货币
        quote_currencies = ["USDT", "USDC", "BUSD", "USD"]

        for quote in quote_currencies:
            if symbol.endswith(quote):
                return symbol[:-len(quote)]

        # 降级：取前3个字符（通常是BTC, ETH等）
        return symbol[:3]

    def _calculate_iv_metrics(
        self, calls: List[OptionsContract], puts: List[OptionsContract]
    ) -> Tuple[float, float]:
        """
        计算ATM IV和skew

        Args:
            calls: call期权列表
            puts: put期权列表

        Returns:
            (atm_iv, skew_25delta)
        """
        # 找ATM期权（delta最接近0.5的call）
        atm_iv = 0.0
        if calls:
            # 按delta排序，找最接近0.5的
            calls_with_delta = [c for c in calls if c.delta is not None]
            if calls_with_delta:
                atm_call = min(calls_with_delta, key=lambda c: abs(c.delta - 0.5))
                atm_iv = atm_call.mark_iv

        # 计算25 delta skew (put_iv - call_iv)
        skew_25delta = 0.0
        calls_25d = [c for c in calls if c.delta and 0.2 <= c.delta <= 0.3]
        puts_25d = [p for p in puts if p.delta and -0.3 <= p.delta <= -0.2]

        if calls_25d and puts_25d:
            avg_call_iv = sum(c.mark_iv for c in calls_25d) / len(calls_25d)
            avg_put_iv = sum(p.mark_iv for p in puts_25d) / len(puts_25d)
            skew_25delta = avg_put_iv - avg_call_iv

        return atm_iv, skew_25delta
