"""
市场微结构计算器

提供本地计算功能:
- VolumeProfileCalculator: 成交量价格分布
- SlippageEstimator: 滑点估算
- TakerFlowAnalyzer: 主动买卖流分析
- OrderbookAggregator: 多场所订单簿聚合
"""
from typing import Dict, List
import statistics


class VolumeProfileCalculator:
    """成交量价格分布计算器"""

    @staticmethod
    def calculate(
        trades: List[Dict], bucket_size: float, price_precision: int = 2
    ) -> Dict:
        """
        计算成交量价格分布

        Args:
            trades: 成交记录列表，每条记录包含 price, qty, side
            bucket_size: 价格桶大小（绝对值）
            price_precision: 价格精度（小数位数）

        Returns:
            包含buckets, poc_price, value_area的字典
        """
        if not trades:
            return {
                "buckets": [],
                "poc_price": 0,
                "value_area_high": 0,
                "value_area_low": 0,
            }

        # 找出价格范围
        prices = [t["price"] for t in trades]
        min_price = min(prices)
        max_price = max(prices)

        # 创建价格桶
        buckets_dict = {}
        current_price = min_price
        while current_price <= max_price:
            bucket_key = round(current_price, price_precision)
            buckets_dict[bucket_key] = {
                "price_low": bucket_key,
                "price_high": round(bucket_key + bucket_size, price_precision),
                "total_volume": 0,
                "buy_volume": 0,
                "sell_volume": 0,
                "trade_count": 0,
                "trades_size": [],
            }
            current_price += bucket_size

        # 分配成交到对应桶
        for trade in trades:
            price = trade["price"]
            qty = trade["qty"]
            side = trade["side"]

            # 找到对应桶
            bucket_key = round(price - (price % bucket_size), price_precision)
            if bucket_key not in buckets_dict:
                # 处理边界情况
                bucket_key = min(
                    buckets_dict.keys(), key=lambda k: abs(k - bucket_key)
                )

            bucket = buckets_dict[bucket_key]
            bucket["total_volume"] += qty
            bucket["trade_count"] += 1
            bucket["trades_size"].append(qty)

            if side == "buy":
                bucket["buy_volume"] += qty
            else:
                bucket["sell_volume"] += qty

        # 计算平均成交大小并转换为列表
        buckets = []
        for bucket in buckets_dict.values():
            if bucket["trade_count"] > 0:
                bucket["avg_trade_size"] = bucket["total_volume"] / bucket[
                    "trade_count"
                ]
            else:
                bucket["avg_trade_size"] = 0
            del bucket["trades_size"]  # 移除临时数据
            buckets.append(bucket)

        # 按成交量排序找POC (Point of Control)
        sorted_by_volume = sorted(buckets, key=lambda b: b["total_volume"], reverse=True)
        poc_price = sorted_by_volume[0]["price_low"] if sorted_by_volume else 0

        # 计算Value Area (70%成交量区间)
        total_volume = sum(b["total_volume"] for b in buckets)
        target_volume = total_volume * 0.7

        # 从POC开始向两边扩展
        value_area_buckets = [sorted_by_volume[0]] if sorted_by_volume else []
        current_volume = sorted_by_volume[0]["total_volume"] if sorted_by_volume else 0

        remaining = sorted_by_volume[1:] if len(sorted_by_volume) > 1 else []
        while current_volume < target_volume and remaining:
            # 选择成交量最大的桶加入value area
            next_bucket = remaining.pop(0)
            value_area_buckets.append(next_bucket)
            current_volume += next_bucket["total_volume"]

        if value_area_buckets:
            value_area_high = max(b["price_high"] for b in value_area_buckets)
            value_area_low = min(b["price_low"] for b in value_area_buckets)
        else:
            value_area_high = value_area_low = 0

        return {
            "buckets": buckets,
            "poc_price": poc_price,
            "value_area_high": value_area_high,
            "value_area_low": value_area_low,
        }


class SlippageEstimator:
    """滑点估算器"""

    @staticmethod
    def estimate(
        orderbook: Dict, order_size_usd: float, side: str, current_price: float
    ) -> Dict:
        """
        估算订单滑点

        Args:
            orderbook: 订单簿数据，包含bids和asks
            order_size_usd: 订单金额(USD)
            side: 买卖方向 "buy" 或 "sell"
            current_price: 当前市价

        Returns:
            包含avg_fill_price, slippage_bps, slippage_usd等信息
        """
        levels = orderbook["asks"] if side == "buy" else orderbook["bids"]

        if not levels:
            return {
                "side": side,
                "order_size_usd": order_size_usd,
                "mid_price": current_price,
                "avg_fill_price": 0,
                "slippage_bps": 0,
                "slippage_usd": 0,
                "filled_quantity": 0,
                "orderbook_depth_sufficient": False,
            }

        # 计算需要的数量
        required_qty = order_size_usd / current_price

        # 模拟吃单过程
        filled_qty = 0
        filled_value = 0
        depth_sufficient = False

        for level in levels:
            price = level["price"]
            available_qty = level["quantity"]

            if filled_qty + available_qty >= required_qty:
                # 这一档可以完全成交
                remaining_qty = required_qty - filled_qty
                filled_qty += remaining_qty
                filled_value += remaining_qty * price
                depth_sufficient = True
                break
            else:
                # 这一档全部吃掉，继续下一档
                filled_qty += available_qty
                filled_value += available_qty * price

        if filled_qty == 0:
            avg_fill_price = 0
            slippage_bps = 0
            slippage_usd = 0
        else:
            avg_fill_price = filled_value / filled_qty
            slippage_bps = abs((avg_fill_price - current_price) / current_price) * 10000
            slippage_usd = abs(filled_value - (filled_qty * current_price))

        return {
            "side": side,
            "order_size_usd": order_size_usd,
            "mid_price": current_price,
            "avg_fill_price": avg_fill_price,
            "slippage_bps": slippage_bps,
            "slippage_usd": slippage_usd,
            "filled_quantity": filled_qty,
            "orderbook_depth_sufficient": depth_sufficient,
        }


class TakerFlowAnalyzer:
    """主动买卖流分析器"""

    @staticmethod
    def analyze(
        trades: List[Dict], large_order_percentile: float = 0.9
    ) -> Dict:
        """
        分析主动买卖流

        Args:
            trades: 成交记录，每条包含 side, qty, quote_qty
            large_order_percentile: 大单阈值百分位数（默认90%）

        Returns:
            包含买卖量统计、大单统计等信息
        """
        if not trades:
            return {
                "total_buy_volume": 0,
                "total_sell_volume": 0,
                "total_buy_count": 0,
                "total_sell_count": 0,
                "net_volume": 0,
                "buy_ratio": 0,
                "large_order_threshold": 0,
                "large_buy_count": 0,
                "large_sell_count": 0,
            }

        buy_trades = [t for t in trades if t["side"] == "buy"]
        sell_trades = [t for t in trades if t["side"] == "sell"]

        total_buy_volume = sum(t["qty"] for t in buy_trades)
        total_sell_volume = sum(t["qty"] for t in sell_trades)
        total_buy_count = len(buy_trades)
        total_sell_count = len(sell_trades)

        net_volume = total_buy_volume - total_sell_volume
        total_volume = total_buy_volume + total_sell_volume
        buy_ratio = total_buy_volume / total_volume if total_volume > 0 else 0

        # 计算大单阈值
        all_sizes = [t["quote_qty"] for t in trades]
        if all_sizes:
            large_order_threshold = statistics.quantiles(
                all_sizes, n=100
            )[int(large_order_percentile * 100) - 1]
        else:
            large_order_threshold = 0

        # 统计大单
        large_buy_count = sum(
            1 for t in buy_trades if t["quote_qty"] >= large_order_threshold
        )
        large_sell_count = sum(
            1 for t in sell_trades if t["quote_qty"] >= large_order_threshold
        )

        return {
            "total_buy_volume": total_buy_volume,
            "total_sell_volume": total_sell_volume,
            "total_buy_count": total_buy_count,
            "total_sell_count": total_sell_count,
            "net_volume": net_volume,
            "buy_ratio": buy_ratio,
            "large_order_threshold": large_order_threshold,
            "large_buy_count": large_buy_count,
            "large_sell_count": large_sell_count,
        }


class OrderbookAggregator:
    """多场所订单簿聚合器"""

    @staticmethod
    def aggregate(orderbooks: List[Dict]) -> Dict:
        """
        聚合多个交易所的订单簿

        Args:
            orderbooks: 订单簿列表，每个包含exchange, bids, asks

        Returns:
            聚合后的订单簿
        """
        if not orderbooks:
            return {
                "exchanges": [],
                "bids": [],
                "asks": [],
                "best_bid": 0,
                "best_ask": 0,
                "global_mid": 0,
                "total_bid_depth_usd": 0,
                "total_ask_depth_usd": 0,
            }

        all_bids = []
        all_asks = []
        exchanges = []

        for ob in orderbooks:
            exchanges.append(ob["exchange"])
            # 添加交易所标识到每个档位
            for bid in ob["bids"]:
                all_bids.append(
                    {
                        "price": bid["price"],
                        "quantity": bid["quantity"],
                        "exchange": ob["exchange"],
                    }
                )
            for ask in ob["asks"]:
                all_asks.append(
                    {
                        "price": ask["price"],
                        "quantity": ask["quantity"],
                        "exchange": ob["exchange"],
                    }
                )

        # 排序并合并相同价格
        all_bids.sort(key=lambda x: x["price"], reverse=True)  # 买单降序
        all_asks.sort(key=lambda x: x["price"])  # 卖单升序

        # 合并相同价格档位
        merged_bids = OrderbookAggregator._merge_levels(all_bids)
        merged_asks = OrderbookAggregator._merge_levels(all_asks)

        # 计算累计量
        merged_bids = OrderbookAggregator._add_cumulative(merged_bids)
        merged_asks = OrderbookAggregator._add_cumulative(merged_asks)

        best_bid = merged_bids[0]["price"] if merged_bids else 0
        best_ask = merged_asks[0]["price"] if merged_asks else 0
        global_mid = (best_bid + best_ask) / 2 if best_bid and best_ask else 0

        # 计算总深度
        total_bid_depth_usd = sum(b["price"] * b["quantity"] for b in all_bids)
        total_ask_depth_usd = sum(a["price"] * a["quantity"] for a in all_asks)

        return {
            "exchanges": list(set(exchanges)),
            "bids": merged_bids[:50],  # 只返回前50档
            "asks": merged_asks[:50],
            "best_bid": best_bid,
            "best_ask": best_ask,
            "global_mid": global_mid,
            "total_bid_depth_usd": total_bid_depth_usd,
            "total_ask_depth_usd": total_ask_depth_usd,
        }

    @staticmethod
    def _merge_levels(levels: List[Dict]) -> List[Dict]:
        """合并相同价格的档位"""
        if not levels:
            return []

        merged = []
        current_price = levels[0]["price"]
        current_qty = levels[0]["quantity"]

        for level in levels[1:]:
            if abs(level["price"] - current_price) < 1e-8:  # 价格相同
                current_qty += level["quantity"]
            else:
                merged.append({"price": current_price, "quantity": current_qty})
                current_price = level["price"]
                current_qty = level["quantity"]

        # 添加最后一个
        merged.append({"price": current_price, "quantity": current_qty})
        return merged

    @staticmethod
    def _add_cumulative(levels: List[Dict]) -> List[Dict]:
        """添加累计量"""
        cumulative = 0
        result = []
        for level in levels:
            cumulative += level["quantity"]
            result.append(
                {
                    "price": level["price"],
                    "quantity": level["quantity"],
                    "total": cumulative,
                }
            )
        return result
