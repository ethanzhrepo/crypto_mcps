"""
macro_hub 工具完整实现

提供宏观经济和市场指标：
- Alternative.me Fear & Greed Index（加密货币恐惧贪婪指数）
- 加密货币市场指数（总市值、BTC占比、ETH占比）
- FRED经济数据（CPI、失业率、GDP、利率等）
- 联储工具（TGA、RRP）
- 传统金融指数（标普500、纳斯达克、VIX等）
- 大宗商品（黄金、原油等）
"""
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import structlog

from src.core.models import (
    CalendarEvent,
    FearGreedIndex,
    IndexData,
    MacroCalendar,
    MacroHubData,
    MacroHubInput,
    MacroHubOutput,
    SourceMeta,
)
from src.data_sources.investing_calendar import InvestingCalendarClient
from src.data_sources.macro import MacroDataClient
from src.data_sources.cme import CMEFedWatchClient
from src.validators import ResponseValidator

logger = structlog.get_logger()


class MacroHubTool:
    """macro_hub工具"""

    def __init__(
        self,
        macro_client: Optional[MacroDataClient] = None,
        fred_client: Optional[Any] = None,
        yfinance_client: Optional[Any] = None,
        calendar_client: Optional[InvestingCalendarClient] = None,
        fedwatch_client: Optional[CMEFedWatchClient] = None,
    ):
        """
        初始化macro_hub工具

        Args:
            macro_client: 宏观数据客户端（加密恐惧贪婪指数）
            fred_client: FRED API客户端（可选）
            yfinance_client: Yahoo Finance客户端（可选）
            calendar_client: Investing.com财经日历客户端（可选）
            fedwatch_client: CME FedWatch客户端（可选）
        """
        self.macro_client = macro_client or MacroDataClient()
        self.fred_client = fred_client
        self.yfinance_client = yfinance_client
        self.calendar_client = calendar_client or InvestingCalendarClient()
        self.fedwatch_client = fedwatch_client
        logger.info(
            "macro_hub_tool_initialized",
            has_fred=fred_client is not None,
            has_yfinance=yfinance_client is not None,
            has_calendar=True,
            has_fedwatch=fedwatch_client is not None,
        )

    async def execute(
        self, params
    ) -> MacroHubOutput:
        """执行macro_hub查询"""
        # 如果传入字典，转换为Pydantic模型
        if isinstance(params, dict):
            params = MacroHubInput(**params)

        start_time = time.time()
        logger.info(
            "macro_hub_execute_start",
            mode=params.mode,
            country=params.country,
        )

        data = MacroHubData()
        source_metas = []
        warnings = []

        # 确定要获取的数据类型
        fetch_all = params.mode == "dashboard"
        fetch_fear_greed = fetch_all or params.mode == "fear_greed"
        fetch_crypto_indices = fetch_all or params.mode == "crypto_indices"
        fetch_fed = fetch_all or params.mode == "fed"
        fetch_indices = fetch_all or params.mode == "indices"
        fetch_calendar = fetch_all or params.mode == "calendar"

        # 恐惧贪婪指数
        if fetch_fear_greed:
            try:
                fg_index, meta = await self._fetch_fear_greed()
                data.fear_greed = fg_index
                source_metas.append(meta)
            except Exception as e:
                logger.warning(f"Failed to fetch fear & greed index: {e}")
                warnings.append(f"Fear & Greed fetch failed: {str(e)}")

        # 加密货币指数
        if fetch_crypto_indices:
            try:
                crypto_indices, meta = await self._fetch_crypto_indices()
                data.crypto_indices = crypto_indices
                source_metas.append(meta)
            except Exception as e:
                logger.warning(f"Failed to fetch crypto indices: {e}")
                warnings.append(f"Crypto indices fetch failed: {str(e)}")

        # FED数据（FRED API）
        if fetch_fed:
            if self.fred_client:
                try:
                    fed_data, meta = await self._fetch_fed_data()
                    # 商用服务器：空数据检测
                    if not fed_data or len(fed_data) == 0:
                        logger.error("fred_returned_empty_data", mode=params.mode)
                        warnings.append("FED API返回空数据，请检查FRED_API_KEY或API配额")
                    else:
                        data.fed = fed_data
                        source_metas.append(meta)
                except Exception as e:
                    logger.error("fred_fetch_failed", error=str(e), exc_info=True)
                    warnings.append(f"FED数据获取失败: {str(e)}")
            else:
                warnings.append(
                    "FED数据需要FRED_API_KEY "
                    "Sign up at https://fredaccount.stlouisfed.org/apikeys"
                )

        # 传统金融指数（Yahoo Finance）
        if fetch_indices:
            if self.yfinance_client:
                try:
                    indices_data, meta = await self._fetch_market_indices()
                    # 商用服务器：空数据检测
                    if not indices_data or len(indices_data) == 0:
                        logger.error("yfinance_returned_empty_data", mode=params.mode)
                        warnings.append("Yahoo Finance返回空数据，可能是API配额或网络问题")
                        data.indices = []  # 设置为空列表而不是保持None
                    else:
                        data.indices = indices_data
                        source_metas.append(meta)
                except Exception as e:
                    logger.error("market_indices_fetch_failed", error=str(e), exc_info=True)
                    warnings.append(f"传统指数获取失败: {str(e)}")
                    data.indices = []  # 异常时也设置为空列表
            else:
                warnings.append(
                    "传统指数需要Yahoo Finance client (无需API key，但客户端未初始化)"
                )

        # 财经日历（Investing.com）
        if fetch_calendar:
            try:
                calendar_data, meta = await self._fetch_calendar(
                    days=params.calendar_days,
                    min_importance=params.calendar_min_importance,
                )
                data.calendar = calendar_data
                source_metas.append(meta)
            except Exception as e:
                logger.warning(f"Failed to fetch economic calendar: {e}")
                warnings.append(f"Economic calendar fetch failed: {str(e)}")

        # TODO: 实现ETF资金流数据 (BTC/ETH ETF Fund Flows)
        # 需要集成以下数据源:
        # 1. Bloomberg/Reuters API (商业数据源):
        #    - 提供美国/欧洲BTC/ETH现货ETF的每日资金流入/流出数据
        #    - 需要付费订阅
        # 2. SEC EDGAR API (免费，但数据滞后):
        #    - https://www.sec.gov/cgi-bin/browse-edgar
        #    - 解析ETF的13F持仓报告
        #    - 数据更新频率: 季度
        # 3. ETF.com / ETFdb API:
        #    - 提供ETF资产规模(AUM)和每日流入流出数据
        #    - 部分数据免费，详细数据需付费
        # 4. 爬虫方案 (备选):
        #    - 爬取Farside Investors数据 (https://farside.co.uk)
        #    - 提供BTC/ETH ETF每日资金流数据可视化
        #    - 需要实现HTML解析逻辑
        # 返回数据结构:
        #   - date: 数据日期
        #   - etf_ticker: ETF代码 (如IBIT, FBTC, ETHA等)
        #   - etf_name: ETF名称
        #   - net_flow_usd: 当日净流入(美元)
        #   - aum_usd: 总资产规模(美元)
        #   - btc_holdings: BTC持仓数量 (仅BTC ETF)
        #   - eth_holdings: ETH持仓数量 (仅ETH ETF)
        # 聚合指标:
        #   - total_btc_etf_flow: 所有BTC ETF总流入
        #   - total_eth_etf_flow: 所有ETH ETF总流入
        #   - btc_etf_aum: BTC ETF总资产规模
        #   - eth_etf_aum: ETH ETF总资产规模
        # ETF flows feature not yet implemented
        # fetch_etf_flows = fetch_all or params.mode == "etf_flows"
        # if fetch_etf_flows:
        #     warnings.append("etf_flows (BTC/ETH ETF fund flows) not yet implemented")

        elapsed = time.time() - start_time
        logger.info(
            "macro_hub_execute_complete",
            elapsed_ms=round(elapsed * 1000, 2),
        )

        # 过滤掉任何意外的 None 或无效的 source_meta 条目，避免响应模型校验失败
        cleaned_source_metas: List[SourceMeta] = []
        for idx, meta in enumerate(source_metas):
            if meta is None:
                logger.warning(
                    "macro_hub_source_meta_none",
                    index=idx,
                    warning="SourceMeta is None and will be ignored",
                )
                continue
            cleaned_source_metas.append(meta)

        # 商用服务器：数据完整性验证
        validation_issues = ResponseValidator.validate_macro_hub(data, params.mode)
        if validation_issues:
            for issue in validation_issues:
                logger.warning("macro_hub_data_validation_failed", issue=issue, mode=params.mode)
                warnings.append(f"[DATA_VALIDATION] {issue}")

        return MacroHubOutput(
            data=data,
            source_meta=cleaned_source_metas,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )

    async def _fetch_fear_greed(self) -> Tuple[FearGreedIndex, SourceMeta]:
        """获取恐惧贪婪指数"""
        data, meta = await self.macro_client.get_fear_greed_index(limit=1)
        return FearGreedIndex(**data), meta

    async def _fetch_crypto_indices(self) -> Tuple[List[IndexData], SourceMeta]:
        """获取加密货币指数"""
        data, meta = await self.macro_client.get_crypto_indices()
        return [IndexData(**idx) for idx in data], meta

    async def _fetch_fed_data(self) -> Tuple[List[IndexData], SourceMeta]:
        """获取FED数据（FRED API）- 使用增强方法获取YoY和涨跌"""
        results = []

        # 初始化默认 meta 防止 UnboundLocalError
        from src.core.source_meta import SourceMetaBuilder
        meta = SourceMetaBuilder.build(
            provider="fred",
            endpoint="/series",
            ttl_seconds=3600,
        )

        # 通胀指标 - 使用 get_series_with_yoy() 获取YoY年率
        inflation_series = [
            ("CPIAUCSL", "CPI"),
            ("CPILFESL", "CPI Core"),
            ("PCEPI", "PCE"),
            ("PCEPILFE", "PCE Core"),
        ]

        for series_id, name in inflation_series:
            try:
                data, fetched_meta = await self.fred_client.get_series_with_yoy(series_id)
                meta = fetched_meta
                if data.get("value") is not None:
                    results.append(IndexData(
                        name=name,
                        symbol=series_id,
                        value=data["value"],
                        date=data.get("date"),
                        year_over_year_rate=data.get("year_over_year_rate"),
                        units=data.get("units"),
                        change_24h=0.0,  # 通胀数据为月度，无日涨跌
                        change_percent=0.0,
                    ))
            except Exception as e:
                logger.warning(f"Failed to fetch {name} from FRED: {e}")

        # 就业指标 - 使用 get_series_with_yoy() 获取YoY变化
        employment_series = [
            ("UNRATE", "Unemployment Rate"),
            ("PAYEMS", "Nonfarm Payrolls"),
        ]

        for series_id, name in employment_series:
            try:
                data, emp_meta = await self.fred_client.get_series_with_yoy(series_id)
                meta = emp_meta
                if data.get("value") is not None:
                    results.append(IndexData(
                        name=name,
                        symbol=series_id,
                        value=data["value"],
                        date=data.get("date"),
                        year_over_year_rate=data.get("year_over_year_rate"),
                        units=data.get("units"),
                        change_24h=0.0,  # 就业数据为月度，无日涨跌
                        change_percent=0.0,
                    ))
            except Exception as e:
                logger.warning(f"Failed to fetch {name} from FRED: {e}")

        # 国债收益率 - 使用 get_series_with_change() 获取日涨跌
        treasury_series = [
            ("DGS2", "Treasury 2Y Yield"),
            ("DGS10", "Treasury 10Y Yield"),
            ("DGS30", "Treasury 30Y Yield"),
        ]

        for series_id, name in treasury_series:
            try:
                data, yc_meta = await self.fred_client.get_series_with_change(series_id, days=1)
                meta = yc_meta
                if data.get("value") is not None:
                    results.append(IndexData(
                        name=name,
                        symbol=series_id,
                        value=data["value"],
                        date=data.get("date"),
                        units=data.get("units"),
                        change_24h=data.get("change", 0.0),  # 真实日涨跌
                        change_percent=data.get("change_percent", 0.0),
                    ))
            except Exception as e:
                logger.warning(f"Failed to fetch {name} from FRED: {e}")

        # 收益率利差 - 计算10Y-2Y
        try:
            # 获取10Y和2Y最新值
            data_10y, _ = await self.fred_client.get_latest_value("DGS10")
            data_2y, _ = await self.fred_client.get_latest_value("DGS2")

            if data_10y.get("value") is not None and data_2y.get("value") is not None:
                spread = data_10y["value"] - data_2y["value"]
                results.append(IndexData(
                    name="10Y-2Y Yield Spread",
                    symbol="DGS10-DGS2",
                    value=spread,
                    date=data_10y.get("date"),
                    units="Percent",
                    change_24h=0.0,
                    change_percent=0.0,
                ))
        except Exception as e:
            logger.warning(f"Failed to calculate yield spread: {e}")

        # 联储工具（TGA、RRP）- 使用普通 get_latest_value()
        fed_tool_series = [
            ("WTREGEN", "TGA Balance"),
            ("RRPONTSYD", "RRP Balance"),
        ]

        for series_id, name in fed_tool_series:
            try:
                data, ft_meta = await self.fred_client.get_latest_value(series_id)
                meta = ft_meta
                if data.get("value") is not None:
                    results.append(IndexData(
                        name=name,
                        symbol=series_id,
                        value=data["value"],
                        date=data.get("date"),
                        units=data.get("units"),
                        change_24h=0.0,
                        change_percent=0.0,
                    ))
            except Exception as e:
                logger.warning(f"Failed to fetch {name} from FRED: {e}")

        return results, meta

    async def _fetch_market_indices(self) -> Tuple[List[IndexData], SourceMeta]:
        """获取传统市场指数（Yahoo Finance）"""
        results = []

        from src.core.source_meta import SourceMetaBuilder
        meta = SourceMetaBuilder.build(
            provider="yfinance",
            endpoint="/v7/finance/quote",
            ttl_seconds=300,
        )

        # 获取股指（含 Russell 2000）
        try:
            indices_data, meta = await self.yfinance_client.get_market_indices()
            for key, quote in indices_data.items():
                if quote and quote.get("price") is not None:
                    results.append(IndexData(
                        name=quote.get("name", key.upper()),
                        symbol=quote.get("symbol", key),
                        value=quote["price"],
                        change_24h=quote.get("change"),
                        change_percent_24h=quote.get("change_percent"),
                        timestamp=datetime.utcnow().isoformat() + "Z",
                    ))
        except Exception as e:
            logger.warning(f"Failed to fetch market indices from YFinance: {e}")

        # 获取大宗商品
        try:
            commodities_data, comm_meta = await self.yfinance_client.get_commodities()
            for key, quote in commodities_data.items():
                if quote and quote.get("price") is not None:
                    results.append(IndexData(
                        name=quote.get("name", key.upper()),
                        symbol=quote.get("symbol", key),
                        value=quote["price"],
                        change_24h=quote.get("change"),
                        change_percent_24h=quote.get("change_percent"),
                        timestamp=datetime.utcnow().isoformat() + "Z",
                    ))
            meta = comm_meta
        except Exception as e:
            logger.warning(f"Failed to fetch commodities from YFinance: {e}")

        # 获取美元指数
        try:
            dxy_data, dxy_meta = await self.yfinance_client.get_dollar_index()
            if dxy_data and dxy_data.get("price") is not None:
                results.append(IndexData(
                    name="US Dollar Index",
                    symbol=dxy_data.get("symbol", "DX-Y.NYB"),
                    value=dxy_data["price"],
                    change_24h=dxy_data.get("change"),
                    change_percent_24h=dxy_data.get("change_percent"),
                    timestamp=datetime.utcnow().isoformat() + "Z",
                ))
            meta = dxy_meta
        except Exception as e:
            logger.warning(f"Failed to fetch DXY from YFinance: {e}")

        # 获取加密货币（BTC/ETH）
        try:
            btc_data, btc_meta = await self.yfinance_client.get_quote("BTC-USD")
            if btc_data and btc_data.get("price") is not None:
                results.append(IndexData(
                    name="Bitcoin",
                    symbol="BTC-USD",
                    value=btc_data["price"],
                    change_24h=btc_data.get("change"),
                    change_percent_24h=btc_data.get("change_percent"),
                    timestamp=datetime.utcnow().isoformat() + "Z",
                ))
            meta = btc_meta
        except Exception as e:
            logger.warning(f"Failed to fetch BTC from YFinance: {e}")

        try:
            eth_data, eth_meta = await self.yfinance_client.get_quote("ETH-USD")
            if eth_data and eth_data.get("price") is not None:
                results.append(IndexData(
                    name="Ethereum",
                    symbol="ETH-USD",
                    value=eth_data["price"],
                    change_24h=eth_data.get("change"),
                    change_percent_24h=eth_data.get("change_percent"),
                    timestamp=datetime.utcnow().isoformat() + "Z",
                ))
            meta = eth_meta
        except Exception as e:
            logger.warning(f"Failed to fetch ETH from YFinance: {e}")

        return results, meta

    async def _fetch_calendar(
        self, days: int, min_importance: int
    ) -> Tuple[MacroCalendar, SourceMeta]:
        """获取财经日历"""
        events_data, meta = await self.calendar_client.get_upcoming_events(
            days=days, min_importance=min_importance
        )

        # 转换为CalendarEvent对象
        events = [CalendarEvent(**event) for event in events_data]

        return MacroCalendar(
            events=events,
            count=len(events),
            days_ahead=days,
            min_importance=min_importance,
            parsed_at=datetime.utcnow().isoformat() + "Z",
        ), meta
