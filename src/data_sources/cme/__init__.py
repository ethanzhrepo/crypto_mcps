"""
CME Group数据客户端

提供CME市场数据：
- FedWatch Tool利率预期概率
- Fed Funds Futures价格
- FOMC会议日程
"""
from .fedwatch import CMEFedWatchClient

__all__ = ["CMEFedWatchClient"]
