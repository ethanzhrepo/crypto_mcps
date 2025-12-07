"""
衍生品计算模块

提供:
- BasisCalculator: 基差计算（现货-期货价差）
- TermStructureBuilder: 期限结构构建
- LiquidationAnalyzer: 清算数据分析
"""
from datetime import datetime
from typing import Dict, List
import statistics


class BasisCalculator:
    """基差计算器"""

    @staticmethod
    def calculate_basis(spot_price: float, future_price: float) -> Dict:
        """
        计算基差

        Args:
            spot_price: 现货价格
            future_price: 期货价格

        Returns:
            包含绝对基差和百分比基差的字典
        """
        basis_absolute = future_price - spot_price
        basis_percent = (basis_absolute / spot_price) * 100 if spot_price > 0 else 0

        return {
            "basis_absolute": basis_absolute,
            "basis_percent": basis_percent,
        }

    @staticmethod
    def annualize_basis(
        basis_percent: float, days_to_expiry: int
    ) -> float:
        """
        年化基差

        Args:
            basis_percent: 百分比基差
            days_to_expiry: 距离到期天数

        Returns:
            年化基差（百分比）
        """
        if days_to_expiry <= 0:
            return 0.0

        return (basis_percent / days_to_expiry) * 365

    @staticmethod
    def build_basis_curve(
        spot_price: float, futures_contracts: List[Dict]
    ) -> Dict:
        """
        构建基差曲线

        Args:
            spot_price: 现货价格
            futures_contracts: 期货合约列表，每个包含 price, expiry_date, contract_type

        Returns:
            基差曲线数据
        """
        points = []

        for contract in futures_contracts:
            future_price = contract["price"]
            basis_result = BasisCalculator.calculate_basis(spot_price, future_price)

            # 计算到期天数
            if contract.get("days_to_expiry"):
                days = contract["days_to_expiry"]
            elif contract.get("expiry_date"):
                try:
                    expiry = datetime.fromisoformat(contract["expiry_date"].replace("Z", ""))
                    days = (expiry - datetime.utcnow()).days
                except:
                    days = 0
            else:
                days = 0

            # 年化基差
            annualized = BasisCalculator.annualize_basis(
                basis_result["basis_percent"], days
            )

            points.append(
                {
                    "contract_type": contract.get("contract_type", "unknown"),
                    "expiry_date": contract.get("expiry_date"),
                    "days_to_expiry": days,
                    "spot_price": spot_price,
                    "future_price": future_price,
                    "basis_absolute": basis_result["basis_absolute"],
                    "basis_percent": basis_result["basis_percent"],
                    "basis_annualized": annualized,
                }
            )

        # 判断升水/贴水
        avg_basis = statistics.mean([p["basis_absolute"] for p in points]) if points else 0
        contango = avg_basis > 0

        return {
            "spot_price": spot_price,
            "points": points,
            "contango": contango,
        }


class TermStructureBuilder:
    """期限结构构建器"""

    @staticmethod
    def build_term_structure(contracts: List[Dict]) -> Dict:
        """
        构建期限结构曲线

        Args:
            contracts: 合约列表，每个包含 expiry_date, implied_yield, open_interest, volume_24h

        Returns:
            期限结构数据
        """
        # 按到期日排序
        sorted_contracts = sorted(
            contracts, key=lambda c: c.get("days_to_expiry", 0)
        )

        curve = []
        for contract in sorted_contracts:
            curve.append(
                {
                    "expiry_date": contract["expiry_date"],
                    "days_to_expiry": contract.get("days_to_expiry", 0),
                    "implied_yield": contract.get("implied_yield", 0),
                    "open_interest": contract.get("open_interest", 0),
                    "volume_24h": contract.get("volume_24h", 0),
                }
            )

        # 判断曲线形态
        if len(curve) < 2:
            slope = "flat"
        else:
            # 比较近期和远期的隐含收益率
            near_term = curve[0]["implied_yield"]
            far_term = curve[-1]["implied_yield"]

            if far_term > near_term + 0.5:  # 阈值0.5%
                slope = "normal"  # 正常（向上倾斜）
            elif near_term > far_term + 0.5:
                slope = "inverted"  # 倒挂（向下倾斜）
            else:
                slope = "flat"

        return {"curve": curve, "slope": slope}


class LiquidationAnalyzer:
    """清算数据分析器"""

    @staticmethod
    def aggregate_liquidations(events: List[Dict]) -> Dict:
        """
        聚合清算事件

        Args:
            events: 清算事件列表，每个包含 side, value_usd

        Returns:
            聚合统计
        """
        if not events:
            return {
                "total_liquidations": 0,
                "total_value_usd": 0,
                "long_liquidations": 0,
                "long_value_usd": 0,
                "short_liquidations": 0,
                "short_value_usd": 0,
            }

        long_events = [e for e in events if e["side"] in ["LONG", "BUY"]]
        short_events = [e for e in events if e["side"] in ["SHORT", "SELL"]]

        long_value = sum(e["value_usd"] for e in long_events)
        short_value = sum(e["value_usd"] for e in short_events)

        return {
            "total_liquidations": len(events),
            "total_value_usd": long_value + short_value,
            "long_liquidations": len(long_events),
            "long_value_usd": long_value,
            "short_liquidations": len(short_events),
            "short_value_usd": short_value,
        }
