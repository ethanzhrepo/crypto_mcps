"""
衍生品计算模块单元测试
"""
import pytest
from datetime import datetime, timedelta

from src.tools.derivatives.calculations import (
    BasisCalculator,
    TermStructureBuilder,
    LiquidationAnalyzer,
)


class TestBasisCalculator:
    """BasisCalculator测试"""

    def test_calculate_basis_contango(self):
        """测试升水情况（期货价格>现货价格）"""
        result = BasisCalculator.calculate_basis(
            spot_price=95000.0,
            future_price=96000.0
        )

        assert result["basis_absolute"] == 1000.0
        assert result["basis_percent"] == pytest.approx(1.053, rel=0.01)

    def test_calculate_basis_backwardation(self):
        """测试贴水情况（期货价格<现货价格）"""
        result = BasisCalculator.calculate_basis(
            spot_price=95000.0,
            future_price=94000.0
        )

        assert result["basis_absolute"] == -1000.0
        assert result["basis_percent"] == pytest.approx(-1.053, rel=0.01)

    def test_calculate_basis_zero_spot_price(self):
        """测试现货价格为0的边缘情况"""
        result = BasisCalculator.calculate_basis(
            spot_price=0.0,
            future_price=96000.0
        )

        assert result["basis_absolute"] == 96000.0
        assert result["basis_percent"] == 0.0

    def test_annualize_basis_normal(self):
        """测试正常年化基差"""
        annualized = BasisCalculator.annualize_basis(
            basis_percent=1.0,  # 1% basis
            days_to_expiry=30   # 30天到期
        )

        # 应该约等于 (1 / 30) * 365 = 12.17%
        assert annualized == pytest.approx(12.17, rel=0.01)

    def test_annualize_basis_zero_days(self):
        """测试0天到期的边缘情况"""
        annualized = BasisCalculator.annualize_basis(
            basis_percent=1.0,
            days_to_expiry=0
        )

        assert annualized == 0.0

    def test_annualize_basis_negative_days(self):
        """测试负天数的边缘情况"""
        annualized = BasisCalculator.annualize_basis(
            basis_percent=1.0,
            days_to_expiry=-5
        )

        assert annualized == 0.0

    def test_build_basis_curve(self):
        """测试构建基差曲线"""
        spot_price = 95000.0
        futures_contracts = [
            {
                "contract_type": "monthly",
                "price": 96000.0,
                "expiry_date": "2025-12-27T00:00:00Z",
                "days_to_expiry": 30,
            },
            {
                "contract_type": "quarterly",
                "price": 97000.0,
                "expiry_date": "2026-03-27T00:00:00Z",
                "days_to_expiry": 90,
            },
        ]

        result = BasisCalculator.build_basis_curve(spot_price, futures_contracts)

        assert result["spot_price"] == 95000.0
        assert len(result["points"]) == 2
        assert result["contango"] is True  # 平均基差 > 0

        # 验证第一个点
        point1 = result["points"][0]
        assert point1["contract_type"] == "monthly"
        assert point1["basis_absolute"] == 1000.0
        assert point1["days_to_expiry"] == 30

    def test_build_basis_curve_backwardation(self):
        """测试贴水曲线"""
        spot_price = 95000.0
        futures_contracts = [
            {
                "contract_type": "monthly",
                "price": 94000.0,
                "days_to_expiry": 30,
            },
            {
                "contract_type": "quarterly",
                "price": 93000.0,
                "days_to_expiry": 90,
            },
        ]

        result = BasisCalculator.build_basis_curve(spot_price, futures_contracts)

        assert result["contango"] is False  # 平均基差 < 0

    def test_build_basis_curve_empty(self):
        """测试空合约列表"""
        result = BasisCalculator.build_basis_curve(95000.0, [])

        assert result["spot_price"] == 95000.0
        assert result["points"] == []
        assert result["contango"] is False  # 默认false（平均为0）


class TestTermStructureBuilder:
    """TermStructureBuilder测试"""

    def test_build_term_structure_normal(self):
        """测试正常期限结构（向上倾斜）"""
        contracts = [
            {
                "expiry_date": "2025-12-27",
                "days_to_expiry": 30,
                "implied_yield": 5.0,
                "open_interest": 10000,
                "volume_24h": 5000,
            },
            {
                "expiry_date": "2026-03-27",
                "days_to_expiry": 90,
                "implied_yield": 6.5,  # 远期更高
                "open_interest": 8000,
                "volume_24h": 3000,
            },
        ]

        result = TermStructureBuilder.build_term_structure(contracts)

        assert len(result["curve"]) == 2
        assert result["slope"] == "normal"  # 正常曲线

    def test_build_term_structure_inverted(self):
        """测试倒挂期限结构（向下倾斜）"""
        contracts = [
            {
                "expiry_date": "2025-12-27",
                "days_to_expiry": 30,
                "implied_yield": 7.0,  # 近期更高
                "open_interest": 10000,
                "volume_24h": 5000,
            },
            {
                "expiry_date": "2026-03-27",
                "days_to_expiry": 90,
                "implied_yield": 5.0,
                "open_interest": 8000,
                "volume_24h": 3000,
            },
        ]

        result = TermStructureBuilder.build_term_structure(contracts)

        assert result["slope"] == "inverted"  # 倒挂曲线

    def test_build_term_structure_flat(self):
        """测试平坦期限结构"""
        contracts = [
            {
                "expiry_date": "2025-12-27",
                "days_to_expiry": 30,
                "implied_yield": 5.5,
                "open_interest": 10000,
                "volume_24h": 5000,
            },
            {
                "expiry_date": "2026-03-27",
                "days_to_expiry": 90,
                "implied_yield": 5.7,  # 差距小于0.5%
                "open_interest": 8000,
                "volume_24h": 3000,
            },
        ]

        result = TermStructureBuilder.build_term_structure(contracts)

        assert result["slope"] == "flat"  # 平坦曲线

    def test_build_term_structure_single_contract(self):
        """测试单个合约"""
        contracts = [
            {
                "expiry_date": "2025-12-27",
                "days_to_expiry": 30,
                "implied_yield": 5.0,
                "open_interest": 10000,
                "volume_24h": 5000,
            },
        ]

        result = TermStructureBuilder.build_term_structure(contracts)

        assert len(result["curve"]) == 1
        assert result["slope"] == "flat"  # 单个合约默认平坦

    def test_build_term_structure_sorting(self):
        """测试合约排序"""
        contracts = [
            {
                "expiry_date": "2026-03-27",
                "days_to_expiry": 90,
                "implied_yield": 6.0,
            },
            {
                "expiry_date": "2025-12-27",
                "days_to_expiry": 30,
                "implied_yield": 5.0,
            },
        ]

        result = TermStructureBuilder.build_term_structure(contracts)

        # 应该按days_to_expiry排序
        assert result["curve"][0]["days_to_expiry"] == 30
        assert result["curve"][1]["days_to_expiry"] == 90

    def test_build_term_structure_empty(self):
        """测试空合约列表"""
        result = TermStructureBuilder.build_term_structure([])

        assert result["curve"] == []
        assert result["slope"] == "flat"


class TestLiquidationAnalyzer:
    """LiquidationAnalyzer测试"""

    def test_aggregate_liquidations_mixed(self):
        """测试混合多空清算"""
        events = [
            {"side": "LONG", "value_usd": 100000},
            {"side": "LONG", "value_usd": 50000},
            {"side": "SHORT", "value_usd": 200000},
            {"side": "SHORT", "value_usd": 150000},
            {"side": "BUY", "value_usd": 30000},  # BUY = LONG
            {"side": "SELL", "value_usd": 40000},  # SELL = SHORT
        ]

        result = LiquidationAnalyzer.aggregate_liquidations(events)

        assert result["total_liquidations"] == 6
        assert result["total_value_usd"] == 570000
        assert result["long_liquidations"] == 3
        assert result["long_value_usd"] == 180000  # 100k + 50k + 30k
        assert result["short_liquidations"] == 3
        assert result["short_value_usd"] == 390000  # 200k + 150k + 40k

    def test_aggregate_liquidations_long_only(self):
        """测试仅多头清算"""
        events = [
            {"side": "LONG", "value_usd": 100000},
            {"side": "BUY", "value_usd": 50000},
        ]

        result = LiquidationAnalyzer.aggregate_liquidations(events)

        assert result["total_liquidations"] == 2
        assert result["total_value_usd"] == 150000
        assert result["long_liquidations"] == 2
        assert result["long_value_usd"] == 150000
        assert result["short_liquidations"] == 0
        assert result["short_value_usd"] == 0

    def test_aggregate_liquidations_short_only(self):
        """测试仅空头清算"""
        events = [
            {"side": "SHORT", "value_usd": 200000},
            {"side": "SELL", "value_usd": 100000},
        ]

        result = LiquidationAnalyzer.aggregate_liquidations(events)

        assert result["total_liquidations"] == 2
        assert result["total_value_usd"] == 300000
        assert result["long_liquidations"] == 0
        assert result["long_value_usd"] == 0
        assert result["short_liquidations"] == 2
        assert result["short_value_usd"] == 300000

    def test_aggregate_liquidations_empty(self):
        """测试空事件列表"""
        result = LiquidationAnalyzer.aggregate_liquidations([])

        assert result["total_liquidations"] == 0
        assert result["total_value_usd"] == 0
        assert result["long_liquidations"] == 0
        assert result["long_value_usd"] == 0
        assert result["short_liquidations"] == 0
        assert result["short_value_usd"] == 0

    def test_aggregate_liquidations_zero_values(self):
        """测试0值清算"""
        events = [
            {"side": "LONG", "value_usd": 0},
            {"side": "SHORT", "value_usd": 0},
        ]

        result = LiquidationAnalyzer.aggregate_liquidations(events)

        assert result["total_liquidations"] == 2
        assert result["total_value_usd"] == 0
        assert result["long_liquidations"] == 1
        assert result["short_liquidations"] == 1
