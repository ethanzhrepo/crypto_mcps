"""
核心数据模型 - Pydantic定义
"""
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ==================== 枚举类型 ====================


class DataSourcePriority(str, Enum):
    """数据源优先级"""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"
    FALLBACK = "fallback"


class ConflictResolutionStrategy(str, Enum):
    """冲突解决策略"""

    PRIMARY_SOURCE = "primary_source"  # 主源优先
    AVERAGE = "average"  # 取平均值
    LATEST_TIMESTAMP = "latest_timestamp"  # 最新时间戳优先
    MANUAL = "manual"  # 需人工判断


# Tool argument enums (exposed via /tools/registry input_schema)
class CryptoOverviewIncludeField(StrEnum):
    ALL = "all"
    BASIC = "basic"
    MARKET = "market"
    SUPPLY = "supply"
    HOLDERS = "holders"
    SOCIAL = "social"
    SECTOR = "sector"
    DEV_ACTIVITY = "dev_activity"


class MarketMicrostructureIncludeField(StrEnum):
    TICKER = "ticker"
    KLINES = "klines"
    TRADES = "trades"
    ORDERBOOK = "orderbook"
    AGGREGATED_ORDERBOOK = "aggregated_orderbook"
    VOLUME_PROFILE = "volume_profile"
    TAKER_FLOW = "taker_flow"
    SLIPPAGE = "slippage"
    VENUE_SPECS = "venue_specs"
    SECTOR_STATS = "sector_stats"
    ALL = "all"


class DerivativesHubIncludeField(StrEnum):
    FUNDING_RATE = "funding_rate"
    OPEN_INTEREST = "open_interest"
    LIQUIDATIONS = "liquidations"
    LONG_SHORT_RATIO = "long_short_ratio"
    BASIS_CURVE = "basis_curve"
    TERM_STRUCTURE = "term_structure"
    OPTIONS_SURFACE = "options_surface"
    OPTIONS_METRICS = "options_metrics"
    BORROW_RATES = "borrow_rates"
    ALL = "all"


# ==================== 基础模型 ====================


class SourceMeta(BaseModel):
    """数据源元信息"""

    provider: str = Field(..., description="数据提供者，如 coingecko, binance")
    endpoint: str = Field(..., description="API端点路径")
    as_of_utc: str = Field(..., description="数据时间戳 (ISO格式)")
    ttl_seconds: int = Field(..., description="缓存TTL（秒）")
    version: str = Field(default="v3", description="数据契约版本")
    degraded: bool = Field(default=False, description="是否降级模式")
    fallback_used: Optional[str] = Field(default=None, description="使用的备用源")
    response_time_ms: Optional[float] = Field(default=None, description="响应时间（毫秒）")

    class Config:
        json_schema_extra = {
            "example": {
                "provider": "coingecko",
                "endpoint": "/coins/bitcoin",
                "as_of_utc": "2025-11-18T12:00:00Z",
                "ttl_seconds": 60,
                "version": "v3",
                "degraded": False,
                "fallback_used": None,
                "response_time_ms": 234.5,
            }
        }


class Conflict(BaseModel):
    """数据冲突记录"""

    field: str = Field(..., description="冲突字段名")
    values: Dict[str, Any] = Field(..., description="各数据源的值")
    diff_percent: Optional[float] = Field(default=None, description="差异百分比")
    diff_absolute: Optional[float] = Field(default=None, description="绝对差异")
    resolution: ConflictResolutionStrategy = Field(..., description="解决策略")
    final_value: Any = Field(..., description="最终采用的值")

    class Config:
        json_schema_extra = {
            "example": {
                "field": "price",
                "values": {"coingecko": 95000, "coinmarketcap": 95100},
                "diff_percent": 0.105,
                "diff_absolute": 100,
                "resolution": "average",
                "final_value": 95050,
            }
        }


# ==================== crypto_overview 工具模型 ====================


class CryptoOverviewInput(BaseModel):
    """crypto_overview输入参数"""

    symbol: str = Field(..., description="代币符号，如 BTC, ETH, ARB")
    token_address: Optional[str] = Field(
        default=None, description="合约地址（可选，用于消歧义）"
    )
    chain: Optional[str] = Field(
        default=None, description="链名称，如 ethereum, bsc, arbitrum"
    )
    vs_currency: str = Field(default="usd", description="计价货币")
    include_fields: List[CryptoOverviewIncludeField] = Field(
        default=[CryptoOverviewIncludeField.ALL],
        description="包含的字段: basic, market, supply, holders, social, sector, dev_activity, all",
    )

    @field_validator("symbol")
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        """符号转大写"""
        return v.upper()


class BasicInfo(BaseModel):
    """基础信息"""

    id: str
    symbol: str
    name: str
    description: Optional[str] = None
    homepage: Optional[List[str]] = None
    blockchain_site: Optional[List[str]] = None
    contract_address: Optional[str] = None
    chain: Optional[str] = None


class MarketMetrics(BaseModel):
    """市场指标"""

    price: float
    market_cap: Optional[float] = None
    market_cap_rank: Optional[int] = None
    fully_diluted_valuation: Optional[float] = None
    total_volume_24h: Optional[float] = None
    high_24h: Optional[float] = None
    low_24h: Optional[float] = None
    price_change_24h: Optional[float] = None
    price_change_percentage_24h: Optional[float] = None
    ath: Optional[float] = None
    atl: Optional[float] = None


class SupplyInfo(BaseModel):
    """供应信息"""

    circulating_supply: Optional[float] = None
    total_supply: Optional[float] = None
    max_supply: Optional[float] = None
    circulating_percent: Optional[float] = None  # 流通占比


class HolderInfo(BaseModel):
    """持有者信息"""

    total_holders: Optional[int] = None
    top10_percent: Optional[float] = None
    top50_percent: Optional[float] = None
    top100_percent: Optional[float] = None
    data_coverage: Optional[str] = None  # 例如: "first_10000_holders"


class SocialInfo(BaseModel):
    """社交信息"""

    twitter_followers: Optional[int] = None
    reddit_subscribers: Optional[int] = None
    telegram_members: Optional[int] = None
    discord_members: Optional[int] = None


class SectorInfo(BaseModel):
    """板块信息"""

    categories: List[str] = Field(default_factory=list)
    primary_category: Optional[str] = None


class DevActivityInfo(BaseModel):
    """开发活跃度"""

    commits_30d: Optional[int] = None
    commits_90d: Optional[int] = None
    contributors_active_30d: Optional[int] = None
    contributors_total: Optional[int] = None
    last_commit_date: Optional[str] = None
    repo_stars: Optional[int] = None
    repo_forks: Optional[int] = None
    trend: Optional[str] = None  # increasing, stable, decreasing


class CryptoOverviewData(BaseModel):
    """crypto_overview完整数据"""

    basic: Optional[BasicInfo] = None
    market: Optional[MarketMetrics] = None
    supply: Optional[SupplyInfo] = None
    holders: Optional[HolderInfo] = None
    social: Optional[SocialInfo] = None
    sector: Optional[SectorInfo] = None
    dev_activity: Optional[DevActivityInfo] = None


class CryptoOverviewOutput(BaseModel):
    """crypto_overview输出"""

    symbol: str
    data: CryptoOverviewData
    source_meta: List[SourceMeta] = Field(default_factory=list)
    conflicts: List[Conflict] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_timestamp(cls, v):
        """格式化时间戳"""
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


# ==================== 通用模型 ====================


class DataSourceConfig(BaseModel):
    """数据源配置"""

    name: str
    priority: DataSourcePriority
    base_url: str
    timeout: float = 10.0
    rate_limit: int = 60  # req/min
    requires_api_key: bool = False
    api_key: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    ttl_seconds: int = 300


class CacheKey(BaseModel):
    """缓存键"""

    tool_name: str
    capability: str
    params_hash: str

    def to_string(self) -> str:
        """转换为字符串格式"""
        return f"{self.tool_name}:{self.capability}:{self.params_hash}"


# ==================== market_microstructure 工具模型 ====================


class MarketMicrostructureInput(BaseModel):
    """market_microstructure输入参数"""

    symbol: str = Field(..., description="交易对符号，如 BTC/USDT, ETH/USDT")
    venues: List[str] = Field(
        default=["binance"],
        description="交易所列表，如 ['binance', 'okx']。支持多场所聚合",
    )
    include_fields: List[MarketMicrostructureIncludeField] = Field(
        default=[MarketMicrostructureIncludeField.TICKER, MarketMicrostructureIncludeField.ORDERBOOK],
        description="返回字段: ticker, klines, trades, orderbook, aggregated_orderbook, "
        "volume_profile, taker_flow, slippage, venue_specs, sector_stats",
    )
    kline_interval: Optional[str] = Field(
        default="1h", description="K线周期: 1m, 5m, 15m, 1h, 4h, 1d"
    )
    kline_limit: int = Field(default=100, description="K线数量")
    orderbook_depth: int = Field(
        default=100,
        description="订单簿深度（建议>=100；过小会导致深度/滑点等分析失真）",
    )
    trades_limit: int = Field(default=100, description="成交记录数量")
    slippage_size_usd: float = Field(
        default=10000, description="滑点估算的订单大小(USD)"
    )


class TickerData(BaseModel):
    """实时行情数据"""

    symbol: str
    exchange: str
    last_price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    spread_bps: Optional[float] = None  # 买卖价差（基点）
    volume_24h: float
    quote_volume_24h: float
    price_change_24h: float
    price_change_percent_24h: float
    high_24h: Optional[float] = None
    low_24h: Optional[float] = None
    timestamp: str


class KlineData(BaseModel):
    """K线数据"""

    open_time: int  # Unix timestamp in ms
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int
    quote_volume: float
    trades_count: Optional[int] = None
    taker_buy_volume: Optional[float] = None
    taker_buy_quote_volume: Optional[float] = None


class TradeData(BaseModel):
    """成交记录"""

    id: str
    price: float
    qty: float
    quote_qty: float
    timestamp: int  # Unix timestamp in ms
    is_buyer_maker: bool  # True = 卖单成交, False = 买单成交
    side: str  # buy/sell (从taker角度)


class OrderbookLevel(BaseModel):
    """订单簿档位"""

    price: float
    quantity: float
    total: float  # 累计量


class OrderbookData(BaseModel):
    """订单簿数据"""

    symbol: str
    exchange: str
    timestamp: int
    bids: List[OrderbookLevel]  # 买单，按价格降序
    asks: List[OrderbookLevel]  # 卖单，按价格升序
    mid_price: float
    spread_bps: float
    bid_depth_10: float  # 前10档买单深度(USD)
    ask_depth_10: float  # 前10档卖单深度(USD)
    imbalance_ratio: Optional[float] = None  # 买卖深度比


class AggregatedOrderbook(BaseModel):
    """多场所聚合订单簿"""

    symbol: str
    exchanges: List[str]
    timestamp: int
    bids: List[OrderbookLevel]
    asks: List[OrderbookLevel]
    best_bid: float
    best_ask: float
    global_mid: float
    total_bid_depth_usd: float
    total_ask_depth_usd: float


class VolumeProfileBucket(BaseModel):
    """成交量价格分布桶"""

    price_low: float
    price_high: float
    total_volume: float
    buy_volume: float
    sell_volume: float
    trade_count: int
    avg_trade_size: float


class VolumeProfile(BaseModel):
    """成交量价格分布"""

    symbol: str
    exchange: str
    time_range_start: int
    time_range_end: int
    bucket_size: float
    buckets: List[VolumeProfileBucket]
    poc_price: float  # Point of Control (最大成交量价格)
    value_area_high: float  # 70%成交量上界
    value_area_low: float  # 70%成交量下界


class TakerFlow(BaseModel):
    """主动买卖流"""

    symbol: str
    exchange: str
    time_range_start: int
    time_range_end: int
    total_buy_volume: float
    total_sell_volume: float
    total_buy_count: int
    total_sell_count: int
    net_volume: float  # buy - sell
    buy_ratio: float  # buy / (buy + sell)
    large_order_threshold: float  # 大单阈值
    large_buy_count: int
    large_sell_count: int


class SlippageEstimate(BaseModel):
    """滑点估算"""

    symbol: str
    exchange: str
    side: str  # buy/sell
    order_size_usd: float
    mid_price: float
    avg_fill_price: float
    slippage_bps: float  # 滑点（基点）
    slippage_usd: float
    filled_quantity: float
    orderbook_depth_sufficient: bool


class VenueSpecs(BaseModel):
    """场所规格"""

    exchange: str
    symbol: str
    base_asset: str
    quote_asset: str
    status: str  # TRADING, HALT, etc.
    tick_size: float  # 最小价格变动
    lot_size: float  # 最小数量变动
    min_notional: float  # 最小订单金额
    maker_fee: float  # 做市商费率
    taker_fee: float  # 吃单费率


class SectorStats(BaseModel):
    """板块统计（基于CoinGecko Categories）"""

    category_id: str  # 板块ID
    name: str  # 板块名称
    market_cap: float  # 总市值
    market_cap_change_24h: float  # 24h市值变化
    volume_24h: Optional[float] = None  # 24h交易量
    updated_at: Optional[str] = None  # 更新时间
    top_3_coins: Optional[List[str]] = None  # 前3币种symbols


class MarketMicrostructureData(BaseModel):
    """market_microstructure完整数据"""

    ticker: Optional[TickerData] = None
    klines: Optional[List[KlineData]] = None
    trades: Optional[List[TradeData]] = None
    orderbook: Optional[OrderbookData] = None
    aggregated_orderbook: Optional[AggregatedOrderbook] = None
    volume_profile: Optional[VolumeProfile] = None
    taker_flow: Optional[TakerFlow] = None
    slippage: Optional[SlippageEstimate] = None
    venue_specs: Optional[VenueSpecs] = None
    sector_stats: Optional[SectorStats] = None


class MarketMicrostructureOutput(BaseModel):
    """market_microstructure输出"""

    symbol: str
    exchange: Optional[str] = None
    data: MarketMicrostructureData
    source_meta: List[SourceMeta] = Field(default_factory=list)
    conflicts: List[Conflict] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_timestamp(cls, v):
        """格式化时间戳"""
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


# ==================== derivatives_hub 工具模型 ====================


class DerivativesHubInput(BaseModel):
    """derivatives_hub输入参数"""

    symbol: str = Field(..., description="交易对符号，如 BTC/USDT, ETH/USDT")
    include_fields: List[DerivativesHubIncludeField] = Field(
        default=[DerivativesHubIncludeField.FUNDING_RATE, DerivativesHubIncludeField.OPEN_INTEREST],
        description="返回字段: funding_rate, open_interest, liquidations, "
        "long_short_ratio, basis_curve, term_structure, options_surface, "
        "options_metrics, borrow_rates",
    )
    lookback_hours: int = Field(default=24, description="清算数据回溯小时数")
    options_expiry: Optional[str] = Field(
        default=None, description="期权到期日，格式: YYMMDD"
    )


class FundingRateData(BaseModel):
    """资金费率数据"""

    symbol: str
    exchange: str
    funding_rate: float  # 当前费率（8小时）
    funding_rate_annual: float  # 年化费率
    next_funding_time: str  # 下次结算时间
    mark_price: float
    index_price: Optional[float] = None
    timestamp: str


class OpenInterestData(BaseModel):
    """未平仓量数据"""

    symbol: str
    exchange: str
    open_interest: float  # 未平仓量（币）
    open_interest_usd: float  # 未平仓量（USD）
    oi_change_24h: Optional[float] = None  # 24h变化
    oi_change_percent_24h: Optional[float] = None
    timestamp: str


class LiquidationEvent(BaseModel):
    """清算事件"""

    symbol: str
    exchange: str
    side: str  # LONG/SHORT
    price: float
    quantity: float
    value_usd: float
    timestamp: int


class LiquidationsData(BaseModel):
    """清算统计"""

    symbol: str
    exchange: str
    time_range_hours: int
    total_liquidations: int
    total_value_usd: float
    long_liquidations: int
    long_value_usd: float
    short_liquidations: int
    short_value_usd: float
    events: List[LiquidationEvent]


class LongShortRatioData(BaseModel):
    """多空比数据"""

    symbol: str
    exchange: str
    ratio_type: str  # accounts/positions/top_accounts
    long_ratio: float  # 多头占比
    short_ratio: float  # 空头占比
    long_short_ratio: float  # 多空比
    timestamp: str


class BasisPoint(BaseModel):
    """基差点"""

    contract_type: str  # perpetual, quarterly, monthly
    expiry_date: Optional[str] = None
    days_to_expiry: Optional[int] = None
    spot_price: float
    future_price: float
    basis_absolute: float  # 绝对基差
    basis_percent: float  # 百分比基差
    basis_annualized: float  # 年化基差


class BasisCurve(BaseModel):
    """基差曲线"""

    symbol: str
    timestamp: str
    spot_price: float
    points: List[BasisPoint]
    contango: bool  # True=升水, False=贴水


class TermStructurePoint(BaseModel):
    """期限结构点"""

    expiry_date: str
    days_to_expiry: int
    implied_yield: float  # 隐含收益率
    open_interest: float
    volume_24h: float


class TermStructure(BaseModel):
    """期限结构"""

    symbol: str
    timestamp: str
    curve: List[TermStructurePoint]
    slope: str  # normal/inverted/flat


class OptionsContract(BaseModel):
    """期权合约"""

    strike: float
    option_type: str  # call/put
    expiry_date: str
    mark_price: float
    mark_iv: float  # 标记隐含波动率
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume_24h: float
    open_interest: float
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    rho: Optional[float] = None


class OptionsSurface(BaseModel):
    """期权曲面"""

    currency: str  # BTC/ETH
    exchange: str
    expiry_date: str
    atm_iv: float  # ATM隐含波动率
    skew_25delta: float  # 25 delta偏斜
    calls: List[OptionsContract]
    puts: List[OptionsContract]
    timestamp: str


class OptionsMetrics(BaseModel):
    """期权市场指标"""

    currency: str
    exchange: str
    dvol_index: Optional[float] = None  # Deribit波动率指数
    put_call_ratio: float  # 看跌/看涨比率
    total_oi_usd: float
    total_volume_24h_usd: float
    iv_rank: Optional[float] = None  # IV百分位
    timestamp: str


class BorrowRate(BaseModel):
    """借贷利率"""

    asset: str
    exchange: str
    hourly_rate: float
    daily_rate: float
    annual_rate: float
    available: float  # 可借额度
    timestamp: str


class BorrowRatesData(BaseModel):
    """借贷利率数据集合"""

    symbol: str
    rates: List[BorrowRate]


class DerivativesHubData(BaseModel):
    """derivatives_hub完整数据"""

    funding_rate: Optional[FundingRateData] = None
    open_interest: Optional[OpenInterestData] = None
    liquidations: Optional[LiquidationsData] = None
    long_short_ratio: Optional[List[LongShortRatioData]] = None
    basis_curve: Optional[BasisCurve] = None
    term_structure: Optional[TermStructure] = None
    options_surface: Optional[OptionsSurface] = None
    options_metrics: Optional[OptionsMetrics] = None
    borrow_rates: Optional[List[BorrowRate]] = None


class DerivativesHubOutput(BaseModel):
    """derivatives_hub输出"""

    symbol: str
    data: DerivativesHubData
    source_meta: List[SourceMeta] = Field(default_factory=list)
    conflicts: List[Conflict] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_timestamp(cls, v):
        """格式化时间戳"""
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


# ==================== onchain_hub 工具模型 ====================


class TVLData(BaseModel):
    """TVL数据"""

    protocol: str
    tvl_usd: float
    tvl_change_24h: Optional[float] = None
    tvl_change_7d: Optional[float] = None
    chain_breakdown: Optional[Dict[str, float]] = None
    timestamp: str


class ProtocolFeesData(BaseModel):
    """协议费用/收入数据"""

    protocol: str
    fees_24h: float
    revenue_24h: float
    fees_7d: float
    revenue_7d: float
    fees_30d: float
    revenue_30d: float
    timestamp: str


class StablecoinMetrics(BaseModel):
    """稳定币指标"""

    stablecoin: str
    total_supply: float
    market_cap: float
    chains: Dict[str, float]  # 各链分布
    dominance: Optional[float] = None  # 市场份额
    timestamp: str


class CEXReservesData(BaseModel):
    """CEX储备数据"""

    exchange: Optional[str] = None  # 特定交易所（如果查询单个）
    total_reserves_usd: float
    token_breakdown: Optional[Dict[str, Any]] = None  # 各币种余额
    chain_distribution: Optional[Dict[str, Any]] = None  # 链上分布
    top_exchanges: Optional[List[Dict[str, Any]]] = None  # 汇总时的前10交易所
    exchange_count: Optional[int] = None  # 交易所数量
    timestamp: str


class BridgeVolumeData(BaseModel):
    """跨链桥交易量数据"""

    bridge: Optional[str] = None  # 特定桥（如果查询单个）
    volume_24h: Optional[float] = None
    volume_7d: Optional[float] = None
    volume_30d: Optional[float] = None
    chains: Optional[List[str]] = None  # 支持的链
    bridges: Optional[List[Dict[str, Any]]] = None  # 所有桥列表
    count: Optional[int] = None  # 桥数量
    timestamp: str


class UniswapV3Pool(BaseModel):
    """Uniswap v3池子数据"""

    pool_address: str
    token0: Dict[str, Any]  # {address, symbol, name, decimals}
    token1: Dict[str, Any]
    fee_tier: int  # 费率基点（如3000 = 0.3%）
    liquidity: float
    sqrt_price: Optional[float] = None
    tick: Optional[int] = None
    token0_price: Optional[float] = None
    token1_price: Optional[float] = None
    tvl_usd: float
    tvl_token0: Optional[float] = None
    tvl_token1: Optional[float] = None
    volume_usd: float
    volume_token0: Optional[float] = None
    volume_token1: Optional[float] = None
    fees_usd: Optional[float] = None
    tx_count: int


class UniswapV3Tick(BaseModel):
    """Uniswap v3 Tick数据（流动性分布）"""

    tick_idx: int
    liquidity_gross: float
    liquidity_net: float
    price0: Optional[float] = None
    price1: Optional[float] = None
    volume_usd: Optional[float] = None
    fees_usd: Optional[float] = None


class DEXLiquidityData(BaseModel):
    """DEX流动性数据"""

    protocol: str  # uniswap_v3, uniswap_v2, curve, etc.
    chain: str  # ethereum, arbitrum, optimism, polygon
    token: Optional[str] = None  # 查询的代币（如果按代币查询）
    pool_address: Optional[str] = None  # 特定池子（如果单池查询）
    total_liquidity_usd: float
    pools: List[Dict[str, Any]]  # 池子列表（通用格式）
    ticks: Optional[List[Dict[str, Any]]] = None  # Tick分布（可选）
    timestamp: str


class GovernanceProposal(BaseModel):
    """治理提案"""

    id: str
    title: str
    state: str  # active, closed, pending
    start_time: str
    end_time: str
    choices: List[str]
    scores: Optional[List[float]] = None
    author: str


class GovernanceData(BaseModel):
    """治理数据"""

    dao: str
    total_proposals: int
    active_proposals: int
    recent_proposals: List[GovernanceProposal]
    timestamp: str


class WhaleTransfer(BaseModel):
    """大额转账记录"""

    tx_hash: str
    timestamp: str
    from_address: str
    from_label: Optional[str] = None  # 地址标签，如 "Binance", "Unknown"
    to_address: str
    to_label: Optional[str] = None
    token_symbol: str
    token_address: Optional[str] = None
    amount: float
    value_usd: float
    chain: str
    blockchain: Optional[str] = None  # whale-alert返回的blockchain名称


class WhaleTransfersData(BaseModel):
    """大额转账数据"""

    token_symbol: Optional[str] = None
    chain: Optional[str] = None
    time_range_hours: int
    min_value_usd: float
    total_transfers: int
    total_value_usd: float
    transfers: List[WhaleTransfer]
    timestamp: str


class TokenUnlockEvent(BaseModel):
    """代币解锁事件"""

    project: str
    token_symbol: str
    unlock_date: str
    unlock_amount: float
    unlock_value_usd: Optional[float] = None
    percentage_of_supply: Optional[float] = None
    cliff_type: str  # cliff, linear, one-time
    description: Optional[str] = None
    source: str


class TokenUnlocksData(BaseModel):
    """代币解锁数据"""

    token_symbol: Optional[str] = None
    upcoming_unlocks: List[TokenUnlockEvent]
    total_locked_value_usd: Optional[float] = None
    next_unlock_date: Optional[str] = None
    timestamp: str


class OnchainActivity(BaseModel):
    """链上活动指标"""

    protocol: Optional[str] = None
    chain: str
    active_addresses_24h: Optional[int] = None
    active_addresses_7d: Optional[int] = None
    transaction_count_24h: Optional[int] = None
    transaction_count_7d: Optional[int] = None
    gas_used_24h: Optional[float] = None
    avg_gas_price_gwei: Optional[float] = None
    new_addresses_24h: Optional[int] = None
    timestamp: str


class ContractRisk(BaseModel):
    """合约风险评估"""

    contract_address: str
    chain: str
    risk_score: Optional[float] = None  # 0-100，越高风险越大
    risk_level: str  # low, medium, high, critical
    provider: str  # goplus 或 slither

    # GoPlus安全检查结果
    is_open_source: Optional[bool] = None
    is_proxy: Optional[bool] = None
    is_mintable: Optional[bool] = None
    can_take_back_ownership: Optional[bool] = None
    owner_change_balance: Optional[bool] = None
    hidden_owner: Optional[bool] = None
    selfdestruct: Optional[bool] = None
    external_call: Optional[bool] = None

    # 代币特定风险
    buy_tax: Optional[float] = None
    sell_tax: Optional[float] = None
    is_honeypot: Optional[bool] = None
    holder_count: Optional[int] = None

    # Slither分析结果
    vulnerabilities: Optional[List[str]] = None
    vulnerability_count: Optional[int] = None
    high_severity_count: Optional[int] = None
    medium_severity_count: Optional[int] = None
    low_severity_count: Optional[int] = None

    # 通用
    audit_status: Optional[str] = None  # audited, unaudited, partial
    auditors: Optional[List[str]] = None
    warnings: Optional[List[str]] = None
    timestamp: str


class OnchainTVLFeesInput(BaseModel):
    """onchain_tvl_fees 输入参数"""

    protocol: str = Field(..., description="协议名称，如 uniswap, aave")
    chain: Optional[str] = Field(
        default=None,
        description="链名称，如 ethereum, arbitrum, optimism, polygon（可选，用于过滤或标注）",
    )


class OnchainTVLFeesOutput(BaseModel):
    """onchain_tvl_fees 输出"""

    protocol: str
    chain: Optional[str] = None
    tvl: TVLData
    protocol_fees: ProtocolFeesData
    source_meta: List[SourceMeta] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_timestamp(cls, v):
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


class OnchainStablecoinsCEXInput(BaseModel):
    """onchain_stablecoins_cex 输入参数"""

    exchange: Optional[str] = Field(
        default=None,
        description="可选的 CEX 名称，如 binance, coinbase；为空时返回汇总",
    )


class OnchainStablecoinsCEXOutput(BaseModel):
    """onchain_stablecoins_cex 输出"""

    stablecoin_metrics: List[StablecoinMetrics]
    cex_reserves: Optional[CEXReservesData] = None
    source_meta: List[SourceMeta] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_timestamp(cls, v):
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


class OnchainBridgeVolumesInput(BaseModel):
    """onchain_bridge_volumes 输入参数"""

    bridge: Optional[str] = Field(
        default=None,
        description="Bridge 名称，如 stargate, hop；为空时返回汇总",
    )


class OnchainBridgeVolumesOutput(BaseModel):
    """onchain_bridge_volumes 输出"""

    bridge_volumes: BridgeVolumeData
    source_meta: List[SourceMeta] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_timestamp(cls, v):
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


class OnchainDEXLiquidityInput(BaseModel):
    """onchain_dex_liquidity 输入参数"""

    chain: str = Field(..., description="链名称，如 ethereum, arbitrum, optimism, polygon")
    token_address: Optional[str] = Field(
        default=None,
        description="代币合约地址（用于按代币查询池子）",
    )
    pool_address: Optional[str] = Field(
        default=None,
        description="Uniswap v3 池子地址（用于单池查询）",
    )
    include_ticks: bool = Field(
        default=False,
        description="是否包含 tick 分布（仅在提供 pool_address 时有效）",
    )


class OnchainDEXLiquidityOutput(BaseModel):
    """onchain_dex_liquidity 输出"""

    dex_liquidity: DEXLiquidityData
    source_meta: List[SourceMeta] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_timestamp(cls, v):
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


class OnchainGovernanceInput(BaseModel):
    """onchain_governance 输入参数"""

    chain: str = Field(
        default="ethereum",
        description="链名称，用于链上治理（Tally） chain_id 映射",
    )
    snapshot_space: Optional[str] = Field(
        default=None,
        description="Snapshot 空间 ID，如 uniswap.eth",
    )
    governor_address: Optional[str] = Field(
        default=None,
        description="链上治理合约地址（用于 Tally）",
    )


class OnchainGovernanceOutput(BaseModel):
    """onchain_governance 输出"""

    governance: GovernanceData
    source_meta: List[SourceMeta] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_timestamp(cls, v):
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


class OnchainTokenUnlocksInput(BaseModel):
    """onchain_token_unlocks 输入参数"""

    token_symbol: Optional[str] = Field(
        default=None,
        description="代币符号；为空时可返回热门项目的解锁计划",
    )


class OnchainTokenUnlocksOutput(BaseModel):
    """onchain_token_unlocks 输出"""

    token_unlocks: TokenUnlocksData
    source_meta: List[SourceMeta] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_timestamp(cls, v):
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


class OnchainActivityInput(BaseModel):
    """onchain_activity 输入参数"""

    chain: str = Field(..., description="链名称，如 ethereum, arbitrum, optimism, polygon")
    protocol: Optional[str] = Field(
        default=None,
        description="可选协议名称，用于标注或过滤",
    )


class OnchainActivityOutput(BaseModel):
    """onchain_activity 输出"""

    activity: OnchainActivity
    source_meta: List[SourceMeta] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_timestamp(cls, v):
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


class OnchainContractRiskInput(BaseModel):
    """onchain_contract_risk 输入参数"""

    contract_address: str = Field(..., description="合约地址")
    chain: str = Field(..., description="链名称，如 ethereum, arbitrum, optimism, polygon")
    provider: Optional[str] = Field(
        default=None,
        description="风险分析提供商：goplus 或 slither（可选）",
    )


class OnchainContractRiskOutput(BaseModel):
    """onchain_contract_risk 输出"""

    contract_risk: ContractRisk
    source_meta: List[SourceMeta] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_timestamp(cls, v):
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


class OnchainAnalyticsInput(BaseModel):
    """onchain_analytics 输入参数"""

    symbol: str = Field(
        default="BTC",
        description="资产符号（BTC, ETH）",
    )
    include_fields: List[str] = Field(
        default_factory=lambda: ["all"],
        description="包含的字段：active_addresses, mvrv, sopr, exchange_reserve, exchange_netflow, exchange_inflow, exchange_outflow, miner, funding_rate, all",
    )
    window: str = Field(
        default="day",
        description="时间窗口：hour 或 day",
    )
    limit: int = Field(
        default=30,
        description="数据点数量（1-365）",
        ge=1,
        le=365,
    )


class OnchainAnalyticsOutput(BaseModel):
    """onchain_analytics 输出"""

    symbol: str
    data: Dict[str, Any] = Field(default_factory=dict)
    source_meta: List[SourceMeta] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_timestamp(cls, v):
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


# ==================== web_research_search 工具模型 ====================


class WebResearchInput(BaseModel):
    """web_research_search输入参数"""

    query: str = Field(..., description="搜索关键词")
    scope: str = Field(
        default="web",
        description="搜索范围: web (综合搜索), academic (学术论文), news (新闻资讯)",
    )
    providers: Optional[List[str]] = Field(
        default=None,
        description="搜索提供商列表：web 范围支持 brave, duckduckgo, google, bing, serpapi, kaito；news 范围支持 bing_news/bing, kaito。默认自动选择可用的提供商",
    )
    time_range: Optional[str] = Field(
        default=None,
        description="时间范围过滤: past_24h/day, past_week/7d, past_month/30d, past_year 等，仅在 scope=news 有效",
    )
    limit: int = Field(default=10, description="结果数量")


class SearchResult(BaseModel):
    """搜索结果"""

    model_config = ConfigDict(extra='allow')

    title: str
    url: str
    snippet: str
    source: str
    relevance_score: Optional[float] = None
    published_at: Optional[str] = None


class WebResearchOutput(BaseModel):
    """web_research_search输出"""

    query: str
    results: List[SearchResult]
    total_results: int
    source_meta: List[SourceMeta] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_timestamp(cls, v):
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


# ==================== crypto_news_search 工具模型 ====================


class CryptoNewsSearchInput(BaseModel):
    """crypto_news_search 输入参数"""

    query: Optional[str] = Field(default=None, description="搜索关键词（可选）")
    symbol: Optional[str] = Field(default=None, description="币种符号（可选），如 BTC、ETH")
    limit: int = Field(default=20, ge=1, le=500, description="结果数量（1-500）")
    offset: int = Field(
        default=0,
        ge=0,
        description="分页偏移量，用于获取下一批结果。与 limit 配合使用可实现分页获取 200+ 条新闻",
    )
    sort_by: str = Field(
        default="timestamp",
        description="排序字段：timestamp（最新优先）或 score（相关性优先）",
    )
    time_range: Optional[str] = Field(
        default=None,
        description="时间范围过滤: past_24h/day, past_week/7d, past_month/30d, past_year 等",
    )
    start_time: Optional[int] = Field(
        default=None,
        description="起始时间（Unix 毫秒时间戳，优先级高于 time_range），如 1735689600000",
    )

    @field_validator("symbol")
    @classmethod
    def symbol_uppercase(cls, v: Optional[str]) -> Optional[str]:
        return v.upper() if isinstance(v, str) and v else v

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if v not in {"timestamp", "score"}:
            raise ValueError("sort_by must be 'timestamp' or 'score'")
        return v


class CryptoNewsSearchOutput(BaseModel):
    """crypto_news_search 输出"""

    query: Optional[str] = None
    symbol: Optional[str] = None
    results: List[SearchResult]
    total_results: int
    next_offset: Optional[int] = Field(
        default=None,
        description="下一页的偏移量。如果为 null，表示没有更多结果",
    )
    has_more: bool = Field(
        default=False,
        description="是否还有更多结果可获取",
    )
    source_meta: List[SourceMeta] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_timestamp(cls, v):
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


# ==================== grok_social_trace 工具模型 ====================


class GrokSocialTraceInput(BaseModel):
    """
    grok_social_trace 输入参数

    由上游 LLM 提供一个简洁的关键提示词，用于在 X/Twitter 上进行溯源搜索。
    """

    keyword_prompt: str = Field(
        ...,
        description="来自 LLM 的关键提示词，用于在 X/Twitter 上进行溯源与 deepsearch 分析",
    )
    language: Optional[str] = Field(
        default="auto",
        description="优先使用的语言，例如 zh、en；auto 表示由 Grok 自动判断",
    )


class GrokOriginAccount(BaseModel):
    """消息最初来源账号信息"""

    handle: Optional[str] = Field(default=None, description="账号 @handle")
    display_name: Optional[str] = Field(default=None, description="显示名称")
    user_id: Optional[str] = Field(default=None, description="内部 user id，如有")
    profile_url: Optional[str] = Field(default=None, description="账号主页 URL")
    first_post_url: Optional[str] = Field(default=None, description="溯源到的最早帖子链接")
    first_post_timestamp: Optional[str] = Field(
        default=None, description="最早帖子时间戳，ISO8601"
    )
    followers_count: Optional[int] = Field(
        default=None, description="粉丝数（如能从 Grok 中解析）"
    )
    is_verified: Optional[bool] = Field(
        default=None, description="是否为认证账号（如能从 Grok 中解析）"
    )


class GrokSocialTraceOutput(BaseModel):
    """
    grok_social_trace 输出

    - origin_account: 溯源到的最初来源账号
    - is_likely_promotion: 是否疑似推广信息
    - deepsearch_insights: 基于社交媒体 deepsearch 的解读
    """

    origin_account: Optional[GrokOriginAccount] = Field(
        default=None, description="消息最初来源账号信息（如 Grok 无法确定则为 None）"
    )
    is_likely_promotion: bool = Field(
        default=False, description="该消息是否可能为推广/营销信息"
    )
    promotion_confidence: Optional[float] = Field(
        default=None, description="推广判断置信度，0-1 之间"
    )
    promotion_rationale: Optional[str] = Field(
        default=None, description="为什么认为是/不是推广信息的理由"
    )
    deepsearch_insights: str = Field(
        ...,
        description="基于 Grok 对 X/Twitter 全局数据的 deepsearch 分析，对该消息的含义、传播路径、相关讨论等进行解读",
    )
    evidence_posts: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="用于支持结论的代表性帖子/引用列表（由 Grok 生成的结构化信息，如 tweet_url、author_handle、summary 等）",
    )
    raw_model_response: Optional[str] = Field(
        default=None, description="Grok 的原始文本响应，便于调试和人工审阅"
    )
    as_of_utc: str = Field(
        ...,
        description="本次溯源和 deepsearch 的时间点（UTC ISO8601）",
    )

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_timestamp(cls, v):
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


# ==================== macro_hub 工具模型 ====================


class MacroHubInput(BaseModel):
    """macro_hub输入参数"""

    mode: str = Field(
        default="dashboard",
        description="查询模式: dashboard (全部数据), fed (联储数据), indices (市场指数), "
        "calendar (财经日历), fear_greed (恐惧贪婪指数), crypto_indices (加密货币指数)",
    )
    country: str = Field(default="US", description="国家代码")
    calendar_days: int = Field(
        default=7, description="财经日历未来天数（用于calendar模式）"
    )
    calendar_min_importance: int = Field(
        default=2, description="财经日历最低重要性 (1-3，用于calendar模式)"
    )


class FEDData(BaseModel):
    """美联储数据"""

    fed_rate: float  # 联邦基金利率
    next_meeting_date: str
    rate_probabilities: Dict[str, float]  # 各利率概率
    timestamp: str


class IndexData(BaseModel):
    """指数数据"""

    name: str
    value: float
    change_24h: float = 0.0             # 改为可选，默认0
    change_percent: float = 0.0          # 改为可选，默认0

    # 新增字段（用于FRED宏观指标增强）
    symbol: Optional[str] = None         # FRED系列ID或股票代码
    date: Optional[str] = None           # 数据实际日期（YYYY-MM-DD）
    year_over_year_rate: Optional[float] = None  # YoY年率（百分比）
    units: Optional[str] = None          # 数据单位

    # 兼容字段（用于YFinance）
    timestamp: Optional[str] = None      # ISO时间戳
    change_percent_24h: Optional[float] = None  # YFinance使用的字段名


class FearGreedIndex(BaseModel):
    """恐惧贪婪指数"""

    value: int  # 0-100
    classification: str  # extreme_fear, fear, neutral, greed, extreme_greed
    timestamp: str


class CalendarEvent(BaseModel):
    """财经日历事件"""

    date: Optional[str] = None  # 日期
    time: str  # 时间
    currency: str  # 货币/国家
    importance: int  # 重要性 1-3
    event: str  # 事件名称
    actual: Optional[str] = None  # 实际值
    forecast: Optional[str] = None  # 预测值
    previous: Optional[str] = None  # 前值
    event_id: Optional[str] = None


class MacroCalendar(BaseModel):
    """宏观财经日历"""

    events: List[CalendarEvent]
    count: int
    days_ahead: Optional[int] = None  # 查询的未来天数
    min_importance: Optional[int] = None  # 最低重要性过滤
    parsed_at: str


class MacroHubData(BaseModel):
    """macro_hub完整数据"""

    fed: Optional[List[IndexData]] = None
    indices: Optional[List[IndexData]] = None
    crypto_indices: Optional[List[IndexData]] = None
    fear_greed: Optional[FearGreedIndex] = None
    calendar: Optional[MacroCalendar] = None  # 财经日历


class MacroHubOutput(BaseModel):
    """macro_hub输出"""

    data: MacroHubData
    source_meta: List[SourceMeta] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_timestamp(cls, v):
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


# ==================== new tool models ====================


class EtfFlowsIncludeField(StrEnum):
    FLOWS = "flows"
    HOLDINGS = "holdings"
    ALL = "all"


class EtfFlowsHoldingsInput(BaseModel):
    """etf_flows_holdings 输入参数"""

    dataset: str = Field(default="bitcoin", description="数据集：bitcoin / ethereum")
    url_override: Optional[str] = Field(default=None, description="可选的Farside URL覆盖")
    include_fields: List[EtfFlowsIncludeField] = Field(
        default=[EtfFlowsIncludeField.FLOWS],
        description="返回字段：flows, holdings, all",
    )


class EtfFlowRecord(BaseModel):
    """ETF Flow 记录（原始字段）"""

    data: Dict[str, Any]


class EtfHoldingRecord(BaseModel):
    """ETF 持仓记录（原始字段）"""

    data: Dict[str, Any]


class EtfFlowsHoldingsOutput(BaseModel):
    """etf_flows_holdings 输出"""

    dataset: str
    flows: List[EtfFlowRecord] = Field(default_factory=list)
    holdings: List[EtfHoldingRecord] = Field(default_factory=list)
    source_meta: List[SourceMeta] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_etf_timestamp(cls, v):
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


class CexNetflowReservesInput(BaseModel):
    """cex_netflow_reserves 输入参数"""

    exchange: Optional[str] = Field(default=None, description="交易所名称（如 binance）")
    include_whale_transfers: bool = Field(
        default=False, description="是否附带 Whale Alert 大额转账"
    )
    min_transfer_usd: int = Field(default=500000, description="大额转账最小USD")
    lookback_hours: int = Field(default=24, description="大额转账回溯小时数")


class CexNetflowReservesOutput(BaseModel):
    """cex_netflow_reserves 输出"""

    exchange: Optional[str] = None
    reserves: Dict[str, Any] = Field(default_factory=dict)
    whale_transfers: Optional[WhaleTransfersData] = None
    source_meta: List[SourceMeta] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_cex_timestamp(cls, v):
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


class LendingLiquidationRiskInput(BaseModel):
    """lending_liquidation_risk 输入参数"""

    asset: Optional[str] = Field(default=None, description="资产符号过滤（如 ETH, USDC）")
    protocols: Optional[List[str]] = Field(default=None, description="协议过滤（如 aave）")
    include_liquidations: bool = Field(default=False, description="是否包含清算数据")
    lookback_hours: int = Field(default=24, description="清算数据回溯小时数")


class LendingLiquidationRiskOutput(BaseModel):
    """lending_liquidation_risk 输出"""

    asset: Optional[str] = None
    yields: List[Dict[str, Any]] = Field(default_factory=list)
    liquidations: Optional[LiquidationsData] = None
    source_meta: List[SourceMeta] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_lending_timestamp(cls, v):
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


class StablecoinHealthInput(BaseModel):
    """stablecoin_health 输入参数"""

    symbol: Optional[str] = Field(default=None, description="稳定币符号过滤，如 USDT")
    chains: Optional[List[str]] = Field(default=None, description="链过滤")


class StablecoinHealthOutput(BaseModel):
    """stablecoin_health 输出"""

    symbol: Optional[str] = None
    stablecoins: List[Dict[str, Any]] = Field(default_factory=list)
    source_meta: List[SourceMeta] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_stablecoin_timestamp(cls, v):
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


class OptionsVolSkewInput(BaseModel):
    """options_vol_skew 输入参数"""

    symbol: str = Field(..., description="标的符号，如 BTC 或 ETH")
    expiry: Optional[str] = Field(default=None, description="到期日或合约ID（可选）")
    providers: List[str] = Field(
        default_factory=lambda: ["deribit", "okx", "binance"],
        description="数据源列表：deribit, okx, binance",
    )


class OptionsVolSkewOutput(BaseModel):
    """options_vol_skew 输出"""

    symbol: str
    data: Dict[str, Any] = Field(default_factory=dict)
    source_meta: List[SourceMeta] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_options_timestamp(cls, v):
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


class BlockspaceMevInput(BaseModel):
    """blockspace_mev 输入参数"""

    chain: str = Field(default="ethereum", description="链名称（目前仅支持ethereum）")
    limit: int = Field(default=100, description="MEV-Boost记录数量")


class BlockspaceMevOutput(BaseModel):
    """blockspace_mev 输出"""

    chain: str
    mev_boost: Dict[str, Any] = Field(default_factory=dict)
    gas_oracle: Optional[Dict[str, Any]] = None
    source_meta: List[SourceMeta] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_blockspace_timestamp(cls, v):
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


class HyperliquidMarketIncludeField(StrEnum):
    FUNDING = "funding"
    OPEN_INTEREST = "open_interest"
    ORDERBOOK = "orderbook"
    TRADES = "trades"
    ASSET_CONTEXTS = "asset_contexts"
    ALL = "all"


class HyperliquidMarketInput(BaseModel):
    """hyperliquid_market 输入参数"""

    symbol: str = Field(..., description="标的符号，如 BTC")
    start_time: Optional[int] = Field(
        default=None,
        ge=0,
        description="资金费率起始时间（Unix 毫秒时间戳，仅 funding 生效）",
    )
    end_time: Optional[int] = Field(
        default=None,
        ge=0,
        description="资金费率结束时间（Unix 毫秒时间戳，仅 funding 生效）",
    )
    include_fields: List[HyperliquidMarketIncludeField] = Field(
        default=[HyperliquidMarketIncludeField.ALL],
        description="返回字段：funding, open_interest, orderbook, trades, asset_contexts, all",
    )


class HyperliquidMarketData(BaseModel):
    """hyperliquid_market 数据体"""

    funding: Optional[Any] = None
    open_interest: Optional[Any] = None
    orderbook: Optional[Any] = None
    trades: Optional[Any] = None
    asset_contexts: Optional[Any] = None


class HyperliquidMarketOutput(BaseModel):
    """hyperliquid_market 输出"""

    symbol: str
    data: HyperliquidMarketData
    source_meta: List[SourceMeta] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_hyperliquid_timestamp(cls, v):
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


# ==================== price_history 工具模型 ====================


class PriceHistoryIncludeIndicator(StrEnum):
    """价格历史技术指标选项"""

    SMA = "sma"
    EMA = "ema"
    RSI = "rsi"
    MACD = "macd"
    BOLLINGER = "bollinger"
    ATR = "atr"
    ALL = "all"


class PriceHistoryInput(BaseModel):
    """price_history 输入参数"""

    symbol: str = Field(..., description="交易对符号，如 BTC/USDT, ETH/USDT")
    interval: Literal["1h", "4h", "1d", "1w", "1M"] = Field(
        default="1d", description="K线周期: 1h=小时, 4h=4小时, 1d=日线, 1w=周线, 1M=月线"
    )
    lookback_days: int = Field(
        default=365, ge=7, le=1825, description="回溯天数，默认365天，最多5年"
    )
    include_indicators: List[PriceHistoryIncludeIndicator] = Field(
        default=[
            PriceHistoryIncludeIndicator.SMA,
            PriceHistoryIncludeIndicator.RSI,
            PriceHistoryIncludeIndicator.MACD,
            PriceHistoryIncludeIndicator.BOLLINGER,
        ],
        description="需要计算的技术指标: sma, ema, rsi, macd, bollinger, atr, all",
    )
    indicator_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="指标参数覆盖，如 {'sma_periods': [20, 50, 200], 'rsi_period': 14}",
    )


class OHLCVData(BaseModel):
    """OHLCV K线数据"""

    timestamp: int = Field(description="Unix时间戳(ms)")
    open: float
    high: float
    low: float
    close: float
    volume: float


class PriceHistoryIndicators(BaseModel):
    """技术指标数据"""

    sma: Optional[Dict[str, List[Optional[float]]]] = Field(
        default=None, description="简单移动平均: {sma_20: [...], sma_50: [...], sma_200: [...]}"
    )
    ema: Optional[Dict[str, List[Optional[float]]]] = Field(
        default=None, description="指数移动平均: {ema_12: [...], ema_26: [...]}"
    )
    rsi: Optional[Dict[str, Any]] = Field(
        default=None, description="RSI: {rsi_14: [...], current: 65.5}"
    )
    macd: Optional[Dict[str, Any]] = Field(
        default=None,
        description="MACD: {macd_line: [...], signal_line: [...], histogram: [...], current_signal: 'bullish'}",
    )
    bollinger: Optional[Dict[str, Any]] = Field(
        default=None,
        description="布林带: {upper: [...], middle: [...], lower: [...], bandwidth: 0.15}",
    )
    atr: Optional[Dict[str, Any]] = Field(
        default=None, description="ATR: {atr_14: [...], current: 1500.5}"
    )


class PriceHistoryStatistics(BaseModel):
    """价格统计数据"""

    volatility_30d: Optional[float] = Field(default=None, description="30日年化波动率")
    volatility_90d: Optional[float] = Field(default=None, description="90日年化波动率")
    max_drawdown_30d: Optional[float] = Field(default=None, description="30日最大回撤")
    max_drawdown_90d: Optional[float] = Field(default=None, description="90日最大回撤")
    sharpe_ratio_90d: Optional[float] = Field(
        default=None, description="90日夏普比率(无风险利率5%)"
    )
    current_vs_ath_pct: Optional[float] = Field(default=None, description="相对ATH跌幅%")
    current_vs_atl_pct: Optional[float] = Field(default=None, description="相对ATL涨幅%")
    price_change_7d_pct: Optional[float] = Field(default=None, description="7日价格变化%")
    price_change_30d_pct: Optional[float] = Field(default=None, description="30日价格变化%")
    price_change_90d_pct: Optional[float] = Field(default=None, description="90日价格变化%")


class SupportResistance(BaseModel):
    """支撑阻力位"""

    support_levels: List[float] = Field(default_factory=list, description="支撑位列表")
    resistance_levels: List[float] = Field(default_factory=list, description="阻力位列表")


class PriceHistoryOutput(BaseModel):
    """price_history 输出"""

    symbol: str
    interval: str
    data_points: int = Field(description="数据点数量")
    date_range: Dict[str, str] = Field(description="日期范围: {start: '...', end: '...'}")
    ohlcv: List[OHLCVData] = Field(description="K线数据列表")
    indicators: PriceHistoryIndicators = Field(description="技术指标")
    statistics: PriceHistoryStatistics = Field(description="统计指标")
    support_resistance: SupportResistance = Field(description="支撑/阻力位")
    source_meta: List[SourceMeta] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_price_history_timestamp(cls, v):
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


# ==================== sector_peers 工具模型 ====================


class SectorPeersSortBy(StrEnum):
    """排序字段"""

    MARKET_CAP = "market_cap"
    TVL = "tvl"
    VOLUME_24H = "volume_24h"
    PRICE_CHANGE_7D = "price_change_7d"


class SectorPeersInput(BaseModel):
    """sector_peers 输入参数"""

    symbol: str = Field(..., description="目标代币符号，如 AAVE, UNI")
    limit: int = Field(default=10, ge=3, le=20, description="返回竞品数量")
    sort_by: SectorPeersSortBy = Field(
        default=SectorPeersSortBy.MARKET_CAP, description="排序字段"
    )
    include_metrics: List[str] = Field(
        default=["market", "tvl", "fees", "social"],
        description="包含的对比指标: market, tvl, fees, social",
    )

    @field_validator("symbol")
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        return v.upper()


class PeerInfo(BaseModel):
    """竞品代币信息"""

    rank: int
    symbol: str
    name: str
    is_target: bool = Field(default=False, description="是否为目标代币")
    market_cap: Optional[float] = None
    market_cap_rank: Optional[int] = None
    tvl: Optional[float] = None
    tvl_rank_in_sector: Optional[int] = None
    fees_24h: Optional[float] = None
    fees_7d: Optional[float] = None
    price: Optional[float] = None
    price_change_24h_pct: Optional[float] = None
    price_change_7d_pct: Optional[float] = None
    volume_24h: Optional[float] = None
    holders: Optional[int] = None
    twitter_followers: Optional[int] = None
    github_commits_30d: Optional[int] = None


class SectorComparison(BaseModel):
    """板块对比分析"""

    valuation_ratios: Optional[Dict[str, Any]] = Field(
        default=None, description="估值比率对比"
    )
    fee_multiples: Optional[Dict[str, Any]] = Field(
        default=None, description="费用收入倍数对比"
    )
    market_share: Optional[Dict[str, Any]] = Field(
        default=None, description="市场份额分析"
    )


class SectorStats(BaseModel):
    """板块统计"""

    total_tvl: Optional[float] = None
    total_market_cap: Optional[float] = None
    avg_price_change_7d_pct: Optional[float] = None
    top_performer_7d: Optional[Dict[str, Any]] = None
    worst_performer_7d: Optional[Dict[str, Any]] = None


class SectorPeersOutput(BaseModel):
    """sector_peers 输出"""

    target_symbol: str
    sector: str = Field(description="板块名称，如 'DeFi - Lending'")
    sector_description: Optional[str] = None
    peers: List[PeerInfo] = Field(description="竞品列表")
    comparison: SectorComparison = Field(description="对比分析")
    sector_stats: SectorStats = Field(description="板块统计")
    source_meta: List[SourceMeta] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_sector_peers_timestamp(cls, v):
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v


# ==================== sentiment_aggregator 工具模型 ====================


class SentimentSource(StrEnum):
    """情绪数据源"""

    TELEGRAM = "telegram"
    TWITTER = "twitter"
    NEWS = "news"
    REDDIT = "reddit"


class SentimentAggregatorInput(BaseModel):
    """sentiment_aggregator 输入参数"""

    symbol: str = Field(..., description="代币符号，如 BTC, ETH")
    lookback_hours: int = Field(
        default=24, ge=1, le=168, description="回溯小时数(最多7天)"
    )
    sources: List[SentimentSource] = Field(
        default=[SentimentSource.TELEGRAM, SentimentSource.TWITTER, SentimentSource.NEWS],
        description="数据源列表: telegram, twitter, news, reddit",
    )
    include_raw_samples: bool = Field(
        default=False, description="是否返回原始消息样本"
    )
    sample_limit: int = Field(default=10, ge=1, le=50, description="每个来源的样本数量")

    @field_validator("symbol")
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        return v.upper()


class OverallSentiment(BaseModel):
    """综合情绪"""

    score: int = Field(ge=0, le=100, description="情绪评分 0-100, 50=中性")
    label: Literal["very_bearish", "bearish", "neutral", "bullish", "very_bullish"]
    confidence: int = Field(ge=0, le=100, description="置信度 0-100")
    trend_vs_24h_ago: Optional[Literal["improving", "stable", "declining"]] = None
    trend_vs_7d_ago: Optional[Literal["improving", "stable", "declining"]] = None


class SourceSentimentBreakdown(BaseModel):
    """单源情绪分解"""

    score: int = Field(ge=0, le=100)
    message_count: Optional[int] = None
    tweet_count: Optional[int] = None
    article_count: Optional[int] = None
    post_count: Optional[int] = None
    positive_count: Optional[int] = None
    negative_count: Optional[int] = None
    neutral_count: Optional[int] = None
    key_topics: Optional[List[str]] = None
    top_sources: Optional[List[str]] = None
    influencer_sentiment: Optional[int] = None
    retail_sentiment: Optional[int] = None
    bot_percentage: Optional[float] = None


class SentimentSignal(BaseModel):
    """情绪信号"""

    type: Literal["bullish", "bearish", "warning", "neutral"]
    strength: int = Field(ge=1, le=10, description="信号强度 1-10")
    source: str
    reason: str


class HistoricalSentimentPoint(BaseModel):
    """历史情绪点"""

    timestamp: str
    score: int = Field(ge=0, le=100)


class SentimentAggregatorOutput(BaseModel):
    """sentiment_aggregator 输出"""

    symbol: str
    analysis_period: Dict[str, str] = Field(description="分析周期: {start: '...', end: '...'}")
    overall_sentiment: OverallSentiment = Field(description="综合情绪")
    source_breakdown: Dict[str, SourceSentimentBreakdown] = Field(
        description="分源情绪"
    )
    signals: List[SentimentSignal] = Field(default_factory=list, description="情绪信号")
    historical_sentiment: List[HistoricalSentimentPoint] = Field(
        default_factory=list, description="历史情绪趋势"
    )
    raw_samples: Optional[Dict[str, List[Dict[str, Any]]]] = Field(
        default=None, description="原始消息样本(如果请求)"
    )
    source_meta: List[SourceMeta] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    as_of_utc: str

    @field_validator("as_of_utc", mode="before")
    @classmethod
    def format_sentiment_timestamp(cls, v):
        if isinstance(v, datetime):
            return v.isoformat() + "Z"
        return v
