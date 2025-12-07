"""
FRED (Federal Reserve Economic Data) API客户端

提供美国联邦储备经济数据库访问：
- 经济时间序列（CPI/PCE/GDP/失业率等）
- 货币供应（M2等）
- 利率和收益率曲线
- 联储工具（TGA/RRP）
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.models import SourceMeta
from src.data_sources.base import BaseDataSource


class FREDClient(BaseDataSource):
    """FRED API客户端"""

    # 常用经济序列ID
    COMMON_SERIES = {
        # 通胀指标
        "cpi": "CPIAUCSL",  # 消费者价格指数（所有城市消费者）
        "cpi_core": "CPILFESL",  # 核心CPI（不含食品和能源）
        "pce": "PCEPI",  # 个人消费支出价格指数
        "pce_core": "PCEPILFE",  # 核心PCE
        "ppi": "PPIFGS",  # 生产者价格指数（最终需求商品）
        # 就业指标
        "unemployment": "UNRATE",  # 失业率
        "payrolls": "PAYEMS",  # 非农就业人数
        "participation": "CIVPART",  # 劳动参与率
        # 货币供应
        "m2": "M2SL",  # M2货币供应
        "m2_velocity": "M2V",  # M2流通速度
        # 利率
        "fed_funds": "DFEDTARU",  # 联邦基金目标利率上限
        "fed_funds_lower": "DFEDTARL",  # 联邦基金目标利率下限
        "treasury_10y": "DGS10",  # 10年期国债收益率
        "treasury_2y": "DGS2",  # 2年期国债收益率
        "treasury_30y": "DGS30",  # 30年期国债收益率
        # 联储工具
        "tga": "WTREGEN",  # 财政部一般账户（TGA）
        "rrp": "RRPONTSYD",  # 隔夜逆回购（RRP）
        # 指数
        "dollar_index": "DTWEXBGS",  # 美元指数（广义）
        "vix": "VIXCLS",  # 波动率指数
        "sp500": "SP500",  # 标普500指数
        "gold": "GOLDAMGBD228NLBM",  # 伦敦黄金定盘价
        # GDP
        "gdp": "GDP",  # 国内生产总值
        "gdp_real": "GDPC1",  # 实际GDP
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化FRED客户端

        Args:
            api_key: FRED API密钥（免费注册获取）
                    https://fredaccount.stlouisfed.org/apikeys
        """
        super().__init__(
            name="fred",
            base_url="https://api.stlouisfed.org/fred",
            timeout=15.0,
            requires_api_key=True,
        )
        self.api_key = api_key

        if not self.api_key:
            raise ValueError(
                "FRED API key is required. Get free key at: "
                "https://fredaccount.stlouisfed.org/apikeys"
            )

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            "Accept": "application/json",
            "User-Agent": "hubrium-mcp-server/1.0",
        }

    async def fetch_raw(
        self, endpoint: str, params: Optional[Dict] = None
    ) -> Any:
        """
        获取原始数据

        Args:
            endpoint: API端点
            params: 查询参数

        Returns:
            原始响应数据
        """
        # 添加API key到所有请求
        if params is None:
            params = {}

        params["api_key"] = self.api_key
        params["file_type"] = "json"

        return await self._make_request("GET", endpoint, params)

    def transform(self, raw_data: Any, data_type: str) -> Dict[str, Any]:
        """
        转换原始数据为标准格式

        Args:
            raw_data: 原始API响应
            data_type: 数据类型（series/observations/category）

        Returns:
            标准化数据
        """
        if data_type == "series":
            return self._transform_series(raw_data)
        elif data_type == "observations":
            return self._transform_observations(raw_data)
        elif data_type == "category":
            return self._transform_category(raw_data)
        else:
            return raw_data

    def _transform_series(self, data: Dict) -> Dict:
        """转换序列元数据"""
        if "seriess" not in data or not data["seriess"]:
            return {}

        series = data["seriess"][0]
        return {
            "id": series.get("id"),
            "title": series.get("title"),
            "units": series.get("units"),
            "frequency": series.get("frequency"),
            "seasonal_adjustment": series.get("seasonal_adjustment"),
            "last_updated": series.get("last_updated"),
            "observation_start": series.get("observation_start"),
            "observation_end": series.get("observation_end"),
            "notes": series.get("notes"),
        }

    def _transform_observations(self, data: Dict) -> Dict:
        """转换观测数据"""
        if "observations" not in data:
            return {"observations": []}

        observations = []
        for obs in data["observations"]:
            # 过滤缺失值
            value_str = obs.get("value", ".")
            if value_str == ".":
                continue

            try:
                value = float(value_str)
            except (ValueError, TypeError):
                continue

            observations.append(
                {
                    "date": obs.get("date"),
                    "value": value,
                    "realtime_start": obs.get("realtime_start"),
                    "realtime_end": obs.get("realtime_end"),
                }
            )

        return {
            "observations": observations,
            "count": len(observations),
            "units": data.get("units"),
        }

    def _transform_category(self, data: Dict) -> Dict:
        """转换分类数据"""
        if "categories" not in data:
            return {}

        return {
            "categories": [
                {
                    "id": cat.get("id"),
                    "name": cat.get("name"),
                    "parent_id": cat.get("parent_id"),
                }
                for cat in data["categories"]
            ]
        }

    async def get_series_info(
        self, series_id: str
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取序列元数据

        Args:
            series_id: 序列ID（如 'CPIAUCSL'）

        Returns:
            (序列信息, SourceMeta)
        """
        endpoint = "/series"
        params = {"series_id": series_id}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="series",
            ttl_seconds=86400,  # 24小时（元数据稳定）
        )

    async def get_series_observations(
        self,
        series_id: str,
        observation_start: Optional[str] = None,
        observation_end: Optional[str] = None,
        limit: int = 10000,
        sort_order: str = "desc",
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取序列观测数据

        Args:
            series_id: 序列ID
            observation_start: 开始日期（YYYY-MM-DD）
            observation_end: 结束日期（YYYY-MM-DD）
            limit: 最大返回数量
            sort_order: 排序（'asc' 或 'desc'）

        Returns:
            (观测数据, SourceMeta)
        """
        endpoint = "/series/observations"
        params = {
            "series_id": series_id,
            "limit": limit,
            "sort_order": sort_order,
        }

        if observation_start:
            params["observation_start"] = observation_start
        if observation_end:
            params["observation_end"] = observation_end

        # TTL根据频率调整
        ttl_seconds = 3600  # 默认1小时

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="observations",
            ttl_seconds=ttl_seconds,
        )

    async def get_latest_value(
        self, series_id: str
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取序列最新值

        Args:
            series_id: 序列ID

        Returns:
            (最新观测, SourceMeta)
        """
        data, meta = await self.get_series_observations(
            series_id=series_id,
            limit=1,
            sort_order="desc",
        )

        if data["observations"]:
            latest = data["observations"][0]
            return {
                "series_id": series_id,
                "date": latest["date"],
                "value": latest["value"],
            }, meta
        else:
            return {
                "series_id": series_id,
                "date": None,
                "value": None,
            }, meta

    async def get_multiple_series(
        self, series_ids: List[str], latest_only: bool = True
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        批量获取多个序列

        Args:
            series_ids: 序列ID列表
            latest_only: 是否仅获取最新值

        Returns:
            (多序列数据, SourceMeta)
        """
        results = {}
        last_meta = None

        for series_id in series_ids:
            try:
                if latest_only:
                    data, meta = await self.get_latest_value(series_id)
                else:
                    data, meta = await self.get_series_observations(series_id)

                results[series_id] = data
                last_meta = meta
            except Exception as e:
                results[series_id] = {"error": str(e)}

        return results, last_meta

    async def get_inflation_data(self) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取通胀数据包

        Returns:
            (通胀指标, SourceMeta)
        """
        series_ids = [
            self.COMMON_SERIES["cpi"],
            self.COMMON_SERIES["cpi_core"],
            self.COMMON_SERIES["pce"],
            self.COMMON_SERIES["pce_core"],
        ]

        data, meta = await self.get_multiple_series(series_ids)

        return {
            "cpi": data.get(self.COMMON_SERIES["cpi"]),
            "cpi_core": data.get(self.COMMON_SERIES["cpi_core"]),
            "pce": data.get(self.COMMON_SERIES["pce"]),
            "pce_core": data.get(self.COMMON_SERIES["pce_core"]),
        }, meta

    async def get_employment_data(self) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取就业数据包

        Returns:
            (就业指标, SourceMeta)
        """
        series_ids = [
            self.COMMON_SERIES["unemployment"],
            self.COMMON_SERIES["payrolls"],
            self.COMMON_SERIES["participation"],
        ]

        data, meta = await self.get_multiple_series(series_ids)

        return {
            "unemployment_rate": data.get(self.COMMON_SERIES["unemployment"]),
            "nonfarm_payrolls": data.get(self.COMMON_SERIES["payrolls"]),
            "participation_rate": data.get(self.COMMON_SERIES["participation"]),
        }, meta

    async def get_yield_curve(self) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取收益率曲线

        Returns:
            (收益率曲线数据, SourceMeta)
        """
        series_ids = [
            self.COMMON_SERIES["treasury_2y"],
            self.COMMON_SERIES["treasury_10y"],
            self.COMMON_SERIES["treasury_30y"],
        ]

        data, meta = await self.get_multiple_series(series_ids)

        # 计算利差
        treasury_2y = data.get(self.COMMON_SERIES["treasury_2y"], {})
        treasury_10y = data.get(self.COMMON_SERIES["treasury_10y"], {})

        spread_10y_2y = None
        if (
            treasury_10y.get("value") is not None
            and treasury_2y.get("value") is not None
        ):
            spread_10y_2y = treasury_10y["value"] - treasury_2y["value"]

        return {
            "treasury_2y": treasury_2y,
            "treasury_10y": treasury_10y,
            "treasury_30y": data.get(self.COMMON_SERIES["treasury_30y"]),
            "spread_10y_2y": spread_10y_2y,
            "inverted": spread_10y_2y < 0 if spread_10y_2y is not None else None,
        }, meta

    async def get_fed_tools(self) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取联储工具数据（TGA、RRP）

        Returns:
            (联储工具数据, SourceMeta)
        """
        series_ids = [
            self.COMMON_SERIES["tga"],
            self.COMMON_SERIES["rrp"],
        ]

        data, meta = await self.get_multiple_series(series_ids)

        return {
            "tga": data.get(self.COMMON_SERIES["tga"]),
            "rrp": data.get(self.COMMON_SERIES["rrp"]),
        }, meta

    async def search_series(
        self, search_text: str, limit: int = 10
    ) -> tuple[List[Dict], SourceMeta]:
        """
        搜索序列

        Args:
            search_text: 搜索关键词
            limit: 最大返回数量

        Returns:
            (搜索结果, SourceMeta)
        """
        endpoint = "/series/search"
        params = {
            "search_text": search_text,
            "limit": limit,
        }

        data, meta = await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="raw",
            ttl_seconds=3600,
        )

        # 提取序列列表
        series_list = []
        if "seriess" in data:
            for series in data["seriess"]:
                series_list.append(
                    {
                        "id": series.get("id"),
                        "title": series.get("title"),
                        "units": series.get("units"),
                        "frequency": series.get("frequency"),
                        "last_updated": series.get("last_updated"),
                    }
                )

        return series_list, meta
