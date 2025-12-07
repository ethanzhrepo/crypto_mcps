"""
crypto_overview工具实现
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from src.core.data_source_registry import registry
from src.core.models import (
    BasicInfo,
    Conflict,
    ConflictResolutionStrategy,
    CryptoOverviewData,
    CryptoOverviewInput,
    CryptoOverviewOutput,
    DevActivityInfo,
    HolderInfo,
    MarketMetrics,
    SectorInfo,
    SocialInfo,
    SourceMeta,
    SupplyInfo,
)
from src.data_sources.coingecko.client import CoinGeckoClient
from src.data_sources.coinmarketcap.client import CoinMarketCapClient
from src.data_sources.etherscan.client import EtherscanClient
from src.data_sources.github.client import GitHubClient
from src.utils.config import config
from src.utils.exceptions import AmbiguousSymbolError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CryptoOverviewTool:
    """crypto_overview工具"""

    def __init__(self):
        self.name = "crypto_overview"

    async def execute(self, params) -> CryptoOverviewOutput:
        """
        执行crypto_overview查询

        Args:
            params: 输入参数（可以是字典或CryptoOverviewInput）

        Returns:
            完整的crypto_overview数据
        """
        # 如果传入字典，转换为Pydantic模型
        if isinstance(params, dict):
            params = CryptoOverviewInput(**params)

        logger.info(
            "Executing crypto_overview",
            symbol=params.symbol,
            include_fields=params.include_fields,
        )

        symbol = params.symbol
        include_fields = set(params.include_fields)
        if "all" in include_fields:
            include_fields = {"basic", "market", "supply", "holders", "social", "sector", "dev_activity"}

        # 初始化结果容器
        data = CryptoOverviewData()
        source_metas: List[SourceMeta] = []
        conflicts: List[Conflict] = []
        warnings: List[str] = []

        # 处理去歧义（按Q2策略：默认主链+警告）
        if not params.chain and not params.token_address:
            # 对于常见币种，默认为主链
            if symbol.upper() not in ["BTC", "ETH", "BNB", "SOL", "ADA", "DOT", "AVAX"]:
                warnings.append(
                    f"Symbol '{symbol}' may exist on multiple chains. "
                    "Defaulting to Ethereum mainnet. "
                    "Specify 'chain' or 'token_address' for accuracy."
                )

        # 1. 获取基础信息（CoinGecko主，CMC备）
        if "basic" in include_fields:
            try:
                basic_data, basic_meta = await self._fetch_basic(symbol)
                data.basic = BasicInfo(**basic_data)
                source_metas.append(basic_meta)
            except Exception as e:
                logger.error(f"Failed to fetch basic info", error=str(e))
                warnings.append(f"basic: {str(e)}")

        # 2. 获取市场指标（CoinGecko + CMC双源）
        if "market" in include_fields:
            try:
                market_data, market_metas, market_conflicts = await self._fetch_market_with_cross_check(symbol)
                data.market = MarketMetrics(**market_data)
                source_metas.extend(market_metas)
                conflicts.extend(market_conflicts)
            except Exception as e:
                logger.error(f"Failed to fetch market data", error=str(e))
                warnings.append(f"market: {str(e)}")

        # 3. 获取供应信息
        if "supply" in include_fields:
            try:
                supply_data, supply_meta = await self._fetch_supply(symbol)
                data.supply = SupplyInfo(**supply_data)
                source_metas.append(supply_meta)
            except Exception as e:
                logger.error(f"Failed to fetch supply info", error=str(e))
                warnings.append(f"supply: {str(e)}")

        # 4. 获取持有者信息（需要chain和token_address）
        if "holders" in include_fields:
            if params.chain and params.token_address:
                try:
                    holder_data, holder_meta = await self._fetch_holders(
                        params.chain,
                        params.token_address
                    )
                    data.holders = HolderInfo(**holder_data)
                    source_metas.append(holder_meta)
                except Exception as e:
                    logger.error(f"Failed to fetch holder info", error=str(e))
                    warnings.append(f"holders: {str(e)}")
            else:
                warnings.append(
                    "Holder data requires 'chain' and 'token_address' parameters"
                )

        # 5. 获取社交信息
        if "social" in include_fields:
            try:
                social_data, social_meta = await self._fetch_social(symbol)
                data.social = SocialInfo(**social_data)
                source_metas.append(social_meta)
            except Exception as e:
                logger.error(f"Failed to fetch social info", error=str(e))
                warnings.append(f"social: {str(e)}")

        # 6. 获取板块信息
        if "sector" in include_fields:
            try:
                sector_data, sector_meta = await self._fetch_sector(symbol)
                data.sector = SectorInfo(**sector_data)
                source_metas.append(sector_meta)
            except Exception as e:
                logger.error(f"Failed to fetch sector info", error=str(e))
                warnings.append(f"sector: {str(e)}")

        # 7. 获取开发活跃度（需要从basic info中提取GitHub URL）
        if "dev_activity" in include_fields:
            try:
                if data.basic and data.basic.homepage:
                    github_url = self._extract_github_url(data.basic.homepage)
                    if github_url:
                        dev_data, dev_meta = await self._fetch_dev_activity(github_url)
                        data.dev_activity = DevActivityInfo(**dev_data)
                        source_metas.append(dev_meta)
                    else:
                        warnings.append("No GitHub repository found for dev_activity")
                else:
                    warnings.append("dev_activity requires basic info first")
            except Exception as e:
                logger.error(f"Failed to fetch dev activity", error=str(e))
                warnings.append(f"dev_activity: {str(e)}")

        # 构建输出
        output = CryptoOverviewOutput(
            symbol=symbol.upper(),
            data=data,
            source_meta=source_metas,
            conflicts=conflicts,
            warnings=warnings,
            as_of_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )

        logger.info(
            "crypto_overview completed",
            symbol=symbol,
            fields_fetched=len([f for f in include_fields if getattr(data, f)]),
            conflicts=len(conflicts),
            warnings=len(warnings),
        )

        return output

    async def _fetch_basic(self, symbol: str) -> Tuple[Dict, SourceMeta]:
        """获取基础信息"""
        # 使用Registry的fallback机制
        coingecko = registry.get_source("coingecko")
        if coingecko is None:
            raise ValueError("CoinGecko data source not registered in registry")

        raw_data = await coingecko.get_coin_data(symbol)

        data, meta = await coingecko.fetch(
            endpoint=f"/coins/{raw_data.get('id')}",
            params={},
            data_type="basic",
            ttl_seconds=config.get_ttl(self.name, "basic"),
        )

        return data, meta

    async def _fetch_market_with_cross_check(
        self,
        symbol: str
    ) -> Tuple[Dict, List[SourceMeta], List[Conflict]]:
        """
        获取市场数据并交叉验证（按Q1策略：阈值共识）
        """
        metas = []
        conflicts = []

        # 从CoinGecko获取
        coingecko = registry.get_source("coingecko")
        raw_cg = await coingecko.get_coin_data(symbol)
        cg_data, cg_meta = await coingecko.fetch(
            endpoint=f"/coins/{raw_cg.get('id')}",
            params={},
            data_type="market",
            ttl_seconds=config.get_ttl(self.name, "market"),
        )
        metas.append(cg_meta)

        # 尝试从CMC获取（用于交叉验证）
        try:
            cmc = registry.get_source("coinmarketcap")
            if cmc and cmc.api_key:
                raw_cmc = await cmc.get_coin_quotes(symbol)
                cmc_data, cmc_meta = await cmc.fetch(
                    endpoint="/cryptocurrency/quotes/latest",
                    params={"symbol": symbol},
                    data_type="market",
                    ttl_seconds=config.get_ttl(self.name, "market"),
                )
                metas.append(cmc_meta)

                # 冲突检测（价格）
                price_conflict = self._detect_price_conflict(cg_data, cmc_data)
                if price_conflict:
                    conflicts.append(price_conflict)
                    # 应用冲突解决策略
                    cg_data = self._resolve_price_conflict(cg_data, cmc_data, price_conflict)

        except Exception as e:
            logger.warning(f"CMC cross-check failed, using CoinGecko only", error=str(e))

        return cg_data, metas, conflicts

    def _detect_price_conflict(self, cg_data: Dict, cmc_data: Dict) -> Optional[Conflict]:
        """
        检测价格冲突（按Q1策略）

        Returns:
            Conflict对象或None
        """
        cg_price = cg_data.get("price")
        cmc_price = cmc_data.get("price")

        if not cg_price or not cmc_price:
            return None

        # 计算差异百分比
        diff_percent = abs(cg_price - cmc_price) / cg_price * 100
        threshold = config.get_conflict_threshold("price_diff_percent")

        if diff_percent > threshold:
            # 差异超过阈值，记录冲突
            resolution = ConflictResolutionStrategy.PRIMARY_SOURCE  # 主源优先
            final_value = cg_price
        else:
            # 差异在阈值内，取平均值
            resolution = ConflictResolutionStrategy.AVERAGE
            final_value = (cg_price + cmc_price) / 2

        return Conflict(
            field="price",
            values={"coingecko": cg_price, "coinmarketcap": cmc_price},
            diff_percent=diff_percent,
            diff_absolute=abs(cg_price - cmc_price),
            resolution=resolution,
            final_value=final_value,
        )

    def _resolve_price_conflict(
        self,
        cg_data: Dict,
        cmc_data: Dict,
        conflict: Conflict
    ) -> Dict:
        """应用冲突解决策略"""
        # 更新价格为解决后的值
        cg_data["price"] = conflict.final_value
        return cg_data

    async def _fetch_supply(self, symbol: str) -> Tuple[Dict, SourceMeta]:
        """获取供应信息"""
        coingecko = registry.get_source("coingecko")
        raw_data = await coingecko.get_coin_data(symbol)

        return await coingecko.fetch(
            endpoint=f"/coins/{raw_data.get('id')}",
            params={},
            data_type="supply",
            ttl_seconds=config.get_ttl(self.name, "supply"),
        )

    async def _fetch_holders(self, chain: str, token_address: str) -> Tuple[Dict, SourceMeta]:
        """获取持有者信息（按Q3策略：只计算可获取范围）"""
        etherscan = EtherscanClient(chain=chain, api_key=config.get_api_key(f"{chain}scan"))

        raw_data = await etherscan.get_token_holders(token_address)

        return await etherscan.fetch(
            endpoint="",
            params={"contractaddress": token_address},
            data_type="holders",
            ttl_seconds=config.get_ttl(self.name, "holders"),
        )

    async def _fetch_social(self, symbol: str) -> Tuple[Dict, SourceMeta]:
        """获取社交信息"""
        coingecko = registry.get_source("coingecko")
        raw_data = await coingecko.get_coin_data(symbol)

        return await coingecko.fetch(
            endpoint=f"/coins/{raw_data.get('id')}",
            params={},
            data_type="social",
            ttl_seconds=config.get_ttl(self.name, "social"),
        )

    async def _fetch_sector(self, symbol: str) -> Tuple[Dict, SourceMeta]:
        """获取板块信息"""
        coingecko = registry.get_source("coingecko")
        raw_data = await coingecko.get_coin_data(symbol)

        return await coingecko.fetch(
            endpoint=f"/coins/{raw_data.get('id')}",
            params={},
            data_type="sector",
            ttl_seconds=config.get_ttl(self.name, "sector"),
        )

    async def _fetch_dev_activity(self, github_url: str) -> Tuple[Dict, SourceMeta]:
        """获取开发活跃度（按Q4指标）"""
        github = registry.get_source("github")
        if not github:
            raise ValueError("GitHub data source not registered")

        # 解析GitHub URL
        parsed = GitHubClient.parse_repo_url(github_url)
        if not parsed:
            raise ValueError(f"Invalid GitHub URL: {github_url}")

        owner, repo = parsed

        # 获取开发活跃度数据
        raw_data = await github.get_dev_activity(owner, repo)

        return await github.fetch(
            endpoint=f"/repos/{owner}/{repo}",
            params={},
            data_type="dev_activity",
            ttl_seconds=config.get_ttl(self.name, "dev_activity"),
        )

    @staticmethod
    def _extract_github_url(urls: List[str]) -> Optional[str]:
        """从URL列表中提取GitHub URL"""
        for url in urls:
            if "github.com" in url:
                return url
        return None


# 全局实例
crypto_overview_tool = CryptoOverviewTool()
