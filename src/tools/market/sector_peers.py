"""
sector_peers 工具

获取与目标代币同板块的竞品列表，并返回关键指标对比数据。
用于相对估值和竞争分析。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import structlog

from src.core.models import (
    PeerInfo,
    SectorComparison,
    SectorPeersInput,
    SectorPeersOutput,
    SectorPeersSortBy,
    SectorStats,
    SourceMeta,
)
from src.data_sources.coingecko.client import CoinGeckoClient
from src.data_sources.defillama import DefiLlamaClient

logger = structlog.get_logger()


# 板块映射：将CoinGecko分类映射到更易读的名称
SECTOR_MAPPING = {
    "decentralized-finance-defi": "DeFi",
    "lending-borrowing": "DeFi - Lending",
    "decentralized-exchange": "DeFi - DEX",
    "yield-farming": "DeFi - Yield",
    "liquid-staking-governance": "DeFi - Staking",
    "layer-1": "Layer 1",
    "layer-2": "Layer 2",
    "oracle": "Oracles",
    "gaming": "Gaming",
    "metaverse": "Metaverse",
    "meme-token": "Meme",
    "artificial-intelligence": "AI",
    "real-world-assets": "RWA",
    "infrastructure": "Infrastructure",
    "privacy-coins": "Privacy",
    "stablecoins": "Stablecoins",
}

# 协议slug映射（symbol -> DefiLlama slug）
PROTOCOL_SLUG_MAP = {
    "AAVE": "aave",
    "UNI": "uniswap",
    "COMP": "compound-finance",
    "MKR": "makerdao",
    "CRV": "curve-finance",
    "SUSHI": "sushiswap",
    "BAL": "balancer",
    "LDO": "lido",
    "SNX": "synthetix",
    "YFI": "yearn-finance",
    "CAKE": "pancakeswap",
    "GMX": "gmx",
    "DYDX": "dydx",
    "1INCH": "1inch-network",
    "PENDLE": "pendle",
    "RPL": "rocket-pool",
}


class SectorPeersTool:
    """
    板块竞品对比工具
    
    数据源:
    - CoinGecko: 市场数据、板块分类
    - DefiLlama: TVL和费用数据（可选）
    """
    
    def __init__(
        self,
        coingecko_client: CoinGeckoClient,
        defillama_client: Optional[DefiLlamaClient] = None,
    ):
        self.coingecko = coingecko_client
        self.defillama = defillama_client
        logger.info("sector_peers_tool_initialized")
    
    async def execute(
        self, params: Union[SectorPeersInput, Dict[str, Any]]
    ) -> SectorPeersOutput:
        """
        执行板块竞品分析
        
        Args:
            params: 输入参数
            
        Returns:
            SectorPeersOutput
        """
        if isinstance(params, dict):
            params = SectorPeersInput(**params)
        
        logger.info(
            "sector_peers_execute_start",
            symbol=params.symbol,
            limit=params.limit,
            sort_by=params.sort_by,
        )
        
        warnings: List[str] = []
        source_meta: List[SourceMeta] = []
        
        # 1. 获取目标代币信息和板块
        target_data, meta = await self._get_coin_data(params.symbol)
        source_meta.append(meta)
        
        if not target_data:
            warnings.append(f"No data found for {params.symbol}")
            return self._empty_response(params, warnings, source_meta)
        
        # 获取板块信息
        categories = target_data.get("categories", [])
        primary_category = categories[0] if categories else "unknown"
        sector_name = SECTOR_MAPPING.get(primary_category, primary_category)
        
        # 2. 获取同板块代币列表
        if primary_category and primary_category != "unknown":
            category_coins, cat_meta = await self._get_category_coins(
                primary_category, limit=params.limit + 5
            )
            source_meta.append(cat_meta)
        else:
            category_coins = []
            warnings.append("Could not determine token category")
        
        # 3. 构建竞品列表
        peers = await self._build_peers_list(
            target_symbol=params.symbol,
            target_data=target_data,
            category_coins=category_coins,
            limit=params.limit,
            sort_by=params.sort_by,
            include_metrics=params.include_metrics,
        )
        
        # 4. 获取TVL数据（如果需要且可用）
        if self.defillama and "tvl" in params.include_metrics:
            peers = await self._enrich_with_tvl(peers)
        
        # 5. 计算对比分析
        comparison = self._calculate_comparison(params.symbol, peers)
        
        # 6. 计算板块统计
        sector_stats = self._calculate_sector_stats(peers)
        
        # 7. 按排序字段排序
        peers = self._sort_peers(peers, params.sort_by)
        
        # 重新分配rank
        for i, peer in enumerate(peers):
            peer.rank = i + 1
        
        output = SectorPeersOutput(
            target_symbol=params.symbol,
            sector=sector_name,
            sector_description=f"Tokens in the {sector_name} category",
            peers=peers,
            comparison=comparison,
            sector_stats=sector_stats,
            source_meta=source_meta,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )
        
        logger.info(
            "sector_peers_execute_complete",
            symbol=params.symbol,
            peers_count=len(peers),
        )
        
        return output
    
    async def _get_coin_data(self, symbol: str) -> tuple[Optional[Dict], SourceMeta]:
        """获取代币数据"""
        try:
            data = await self.coingecko.get_coin_data(symbol)
            meta = SourceMeta(
                provider="coingecko",
                endpoint=f"/coins/{symbol.lower()}",
                as_of_utc=datetime.utcnow().isoformat() + "Z",
                ttl_seconds=300,
            )
            return data, meta
        except Exception as e:
            logger.warning(f"Failed to get coin data for {symbol}: {e}")
            return None, SourceMeta(
                provider="coingecko",
                endpoint=f"/coins/{symbol.lower()}",
                as_of_utc=datetime.utcnow().isoformat() + "Z",
                ttl_seconds=300,
                degraded=True,
            )
    
    async def _get_category_coins(
        self, category_id: str, limit: int = 20
    ) -> tuple[List[Dict], SourceMeta]:
        """获取某个分类下的代币列表"""
        try:
            # CoinGecko categories endpoint
            data, meta = await self.coingecko.get_category_detail(category_id)
            # 这里假设返回的是代币列表
            coins = data if isinstance(data, list) else []
            return coins[:limit], meta
        except Exception as e:
            logger.warning(f"Failed to get category coins for {category_id}: {e}")
            return [], SourceMeta(
                provider="coingecko",
                endpoint=f"/coins/categories/{category_id}",
                as_of_utc=datetime.utcnow().isoformat() + "Z",
                ttl_seconds=300,
                degraded=True,
            )
    
    async def _build_peers_list(
        self,
        target_symbol: str,
        target_data: Dict,
        category_coins: List[Dict],
        limit: int,
        sort_by: SectorPeersSortBy,
        include_metrics: List[str],
    ) -> List[PeerInfo]:
        """构建竞品列表"""
        peers = []
        
        # 首先添加目标代币
        target_peer = self._coin_to_peer(target_data, is_target=True, rank=1)
        peers.append(target_peer)
        
        # 添加同板块代币
        for i, coin in enumerate(category_coins):
            coin_symbol = coin.get("symbol", "").upper()
            if coin_symbol == target_symbol:
                continue
            
            peer = self._coin_to_peer(coin, is_target=False, rank=i + 2)
            peers.append(peer)
            
            if len(peers) >= limit:
                break
        
        return peers
    
    def _coin_to_peer(
        self, coin_data: Dict, is_target: bool, rank: int
    ) -> PeerInfo:
        """将CoinGecko代币数据转换为PeerInfo"""
        
        market_data = coin_data.get("market_data", {})
        community_data = coin_data.get("community_data", {})
        
        # 兼容不同的数据格式
        price = market_data.get("current_price", {}).get("usd") if isinstance(market_data.get("current_price"), dict) else market_data.get("current_price")
        market_cap = market_data.get("market_cap", {}).get("usd") if isinstance(market_data.get("market_cap"), dict) else market_data.get("market_cap")
        volume_24h = market_data.get("total_volume", {}).get("usd") if isinstance(market_data.get("total_volume"), dict) else market_data.get("total_volume")
        
        return PeerInfo(
            rank=rank,
            symbol=coin_data.get("symbol", "").upper(),
            name=coin_data.get("name", ""),
            is_target=is_target,
            market_cap=market_cap,
            market_cap_rank=market_data.get("market_cap_rank") or coin_data.get("market_cap_rank"),
            price=price,
            price_change_24h_pct=market_data.get("price_change_percentage_24h"),
            price_change_7d_pct=market_data.get("price_change_percentage_7d"),
            volume_24h=volume_24h,
            twitter_followers=community_data.get("twitter_followers"),
        )
    
    async def _enrich_with_tvl(self, peers: List[PeerInfo]) -> List[PeerInfo]:
        """使用DefiLlama数据丰富TVL信息"""
        if not self.defillama:
            return peers
        
        for peer in peers:
            slug = PROTOCOL_SLUG_MAP.get(peer.symbol)
            if slug:
                try:
                    tvl_data, _ = await self.defillama.get_protocol_tvl(slug)
                    if tvl_data:
                        peer.tvl = tvl_data.get("tvl_usd") or tvl_data.get("tvl")
                except Exception as e:
                    logger.debug(f"Failed to get TVL for {peer.symbol}: {e}")
        
        return peers
    
    def _calculate_comparison(
        self, target_symbol: str, peers: List[PeerInfo]
    ) -> SectorComparison:
        """计算对比分析"""
        
        target_peer = next((p for p in peers if p.is_target), None)
        if not target_peer:
            return SectorComparison()
        
        # 计算板块平均值
        non_target_peers = [p for p in peers if not p.is_target]
        
        # 估值比率
        valuation_ratios = None
        if target_peer.market_cap and target_peer.tvl:
            target_mcap_tvl = target_peer.market_cap / target_peer.tvl if target_peer.tvl > 0 else None
            
            sector_mcap_tvl_values = [
                p.market_cap / p.tvl 
                for p in non_target_peers 
                if p.market_cap and p.tvl and p.tvl > 0
            ]
            sector_avg = sum(sector_mcap_tvl_values) / len(sector_mcap_tvl_values) if sector_mcap_tvl_values else None
            
            if target_mcap_tvl and sector_avg:
                diff_pct = ((target_mcap_tvl - sector_avg) / sector_avg) * 100
                interpretation = "相对低估" if diff_pct < -20 else ("相对高估" if diff_pct > 20 else "估值合理")
                
                valuation_ratios = {
                    "target_mcap_tvl_ratio": round(target_mcap_tvl, 2),
                    "sector_avg_mcap_tvl_ratio": round(sector_avg, 2),
                    "target_vs_sector_pct": round(diff_pct, 1),
                    "interpretation": interpretation,
                }
        
        # 市场份额
        market_share = None
        total_tvl = sum(p.tvl for p in peers if p.tvl)
        total_volume = sum(p.volume_24h for p in peers if p.volume_24h)
        
        if total_tvl > 0 and target_peer.tvl:
            tvl_share = (target_peer.tvl / total_tvl) * 100
            market_share = market_share or {}
            market_share["target_tvl_share_pct"] = round(tvl_share, 1)
        
        if total_volume > 0 and target_peer.volume_24h:
            vol_share = (target_peer.volume_24h / total_volume) * 100
            market_share = market_share or {}
            market_share["target_volume_share_pct"] = round(vol_share, 1)
        
        return SectorComparison(
            valuation_ratios=valuation_ratios,
            market_share=market_share,
        )
    
    def _calculate_sector_stats(self, peers: List[PeerInfo]) -> SectorStats:
        """计算板块统计"""
        
        total_tvl = sum(p.tvl for p in peers if p.tvl) or None
        total_market_cap = sum(p.market_cap for p in peers if p.market_cap) or None
        
        # 7日涨跌幅
        peers_with_change = [p for p in peers if p.price_change_7d_pct is not None]
        avg_change = None
        top_performer = None
        worst_performer = None
        
        if peers_with_change:
            avg_change = sum(p.price_change_7d_pct for p in peers_with_change) / len(peers_with_change)
            
            sorted_by_change = sorted(peers_with_change, key=lambda x: x.price_change_7d_pct or 0, reverse=True)
            if sorted_by_change:
                top = sorted_by_change[0]
                top_performer = {"symbol": top.symbol, "change_pct": top.price_change_7d_pct}
                worst = sorted_by_change[-1]
                worst_performer = {"symbol": worst.symbol, "change_pct": worst.price_change_7d_pct}
        
        return SectorStats(
            total_tvl=total_tvl,
            total_market_cap=total_market_cap,
            avg_price_change_7d_pct=round(avg_change, 2) if avg_change else None,
            top_performer_7d=top_performer,
            worst_performer_7d=worst_performer,
        )
    
    def _sort_peers(
        self, peers: List[PeerInfo], sort_by: SectorPeersSortBy
    ) -> List[PeerInfo]:
        """按指定字段排序"""
        
        key_map = {
            SectorPeersSortBy.MARKET_CAP: lambda p: p.market_cap or 0,
            SectorPeersSortBy.TVL: lambda p: p.tvl or 0,
            SectorPeersSortBy.VOLUME_24H: lambda p: p.volume_24h or 0,
            SectorPeersSortBy.PRICE_CHANGE_7D: lambda p: p.price_change_7d_pct or -9999,
        }
        
        key_func = key_map.get(sort_by, key_map[SectorPeersSortBy.MARKET_CAP])
        return sorted(peers, key=key_func, reverse=True)
    
    def _empty_response(
        self,
        params: SectorPeersInput,
        warnings: List[str],
        source_meta: List[SourceMeta],
    ) -> SectorPeersOutput:
        """返回空响应"""
        
        return SectorPeersOutput(
            target_symbol=params.symbol,
            sector="Unknown",
            peers=[],
            comparison=SectorComparison(),
            sector_stats=SectorStats(),
            source_meta=source_meta,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )


__all__ = ["SectorPeersTool"]
