"""
Binance WebSocket 实时数据客户端

提供实时订阅：
- Ticker (24hr ticker stream)
- Trades (实时成交)
- Depth (订单簿更新)
- Klines (K线更新)
"""
import asyncio
import json
from typing import Any, Callable, Dict, List, Optional

import structlog
import websockets
from websockets.client import WebSocketClientProtocol

logger = structlog.get_logger()


class BinanceWebSocket:
    """Binance WebSocket客户端"""

    WS_BASE_URL = "wss://stream.binance.com:9443/ws"
    COMBINED_STREAM_URL = "wss://stream.binance.com:9443/stream"

    def __init__(self):
        """初始化WebSocket客户端"""
        self.connections: Dict[str, WebSocketClientProtocol] = {}
        self.subscriptions: Dict[str, List[Callable]] = {}
        self.running = False

    async def subscribe_ticker(
        self, symbol: str, callback: Callable[[Dict[str, Any]], None]
    ):
        """
        订阅24小时ticker

        Args:
            symbol: 交易对，如 BTCUSDT
            callback: 回调函数，接收ticker数据
        """
        stream = f"{symbol.lower()}@ticker"
        await self._subscribe(stream, callback)

    async def subscribe_trades(
        self, symbol: str, callback: Callable[[Dict[str, Any]], None]
    ):
        """
        订阅实时成交流

        Args:
            symbol: 交易对
            callback: 回调函数，接收trade数据
        """
        stream = f"{symbol.lower()}@trade"
        await self._subscribe(stream, callback)

    async def subscribe_depth(
        self,
        symbol: str,
        callback: Callable[[Dict[str, Any]], None],
        update_speed: str = "100ms",
    ):
        """
        订阅订单簿更新

        Args:
            symbol: 交易对
            callback: 回调函数，接收depth数据
            update_speed: 更新速度，'100ms' 或 '1000ms'
        """
        stream = f"{symbol.lower()}@depth@{update_speed}"
        await self._subscribe(stream, callback)

    async def subscribe_kline(
        self,
        symbol: str,
        interval: str,
        callback: Callable[[Dict[str, Any]], None],
    ):
        """
        订阅K线更新

        Args:
            symbol: 交易对
            interval: K线间隔，如 '1m', '5m', '1h', '1d'
            callback: 回调函数，接收kline数据
        """
        stream = f"{symbol.lower()}@kline_{interval}"
        await self._subscribe(stream, callback)

    async def subscribe_aggregated_trade(
        self, symbol: str, callback: Callable[[Dict[str, Any]], None]
    ):
        """
        订阅归集交易流

        Args:
            symbol: 交易对
            callback: 回调函数，接收聚合trade数据
        """
        stream = f"{symbol.lower()}@aggTrade"
        await self._subscribe(stream, callback)

    async def subscribe_multiple(
        self, streams: List[str], callback: Callable[[Dict[str, Any]], None]
    ):
        """
        订阅多个stream（组合stream）

        Args:
            streams: stream列表，如 ['btcusdt@ticker', 'ethusdt@ticker']
            callback: 回调函数
        """
        combined_stream = "/".join(streams)
        url = f"{self.COMBINED_STREAM_URL}?streams={combined_stream}"

        # 使用组合URL作为连接key
        conn_key = f"combined_{hash(combined_stream)}"

        if conn_key in self.connections:
            logger.warning(f"Already subscribed to combined stream: {conn_key}")
            return

        self.subscriptions[conn_key] = [callback]
        asyncio.create_task(self._connect_and_listen(url, conn_key))

    async def _subscribe(self, stream: str, callback: Callable):
        """
        内部订阅方法

        Args:
            stream: stream名称
            callback: 回调函数
        """
        if stream not in self.subscriptions:
            self.subscriptions[stream] = []

        self.subscriptions[stream].append(callback)

        # 如果还没有连接，创建连接
        if stream not in self.connections:
            url = f"{self.WS_BASE_URL}/{stream}"
            asyncio.create_task(self._connect_and_listen(url, stream))

    async def _connect_and_listen(self, url: str, stream_key: str):
        """
        连接WebSocket并监听消息

        Args:
            url: WebSocket URL
            stream_key: stream标识（用于查找回调）
        """
        retry_count = 0
        max_retries = 5
        retry_delay = 5  # 秒

        while retry_count < max_retries:
            try:
                logger.info(f"Connecting to WebSocket: {stream_key}")

                async with websockets.connect(url) as websocket:
                    self.connections[stream_key] = websocket
                    logger.info(f"Connected to WebSocket: {stream_key}")

                    # 监听消息
                    async for message in websocket:
                        try:
                            data = json.loads(message)

                            # 处理组合stream格式
                            if "stream" in data and "data" in data:
                                # 组合stream返回格式: {"stream": "btcusdt@ticker", "data": {...}}
                                payload = data["data"]
                            else:
                                # 单stream返回格式直接是数据
                                payload = data

                            # 调用所有订阅的回调
                            if stream_key in self.subscriptions:
                                for callback in self.subscriptions[stream_key]:
                                    try:
                                        if asyncio.iscoroutinefunction(callback):
                                            await callback(payload)
                                        else:
                                            callback(payload)
                                    except Exception as e:
                                        logger.error(
                                            f"Error in callback for {stream_key}: {e}"
                                        )

                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to decode message: {e}")
                        except Exception as e:
                            logger.error(f"Error processing message: {e}")

            except websockets.exceptions.ConnectionClosed:
                logger.warning(f"WebSocket connection closed: {stream_key}")
                retry_count += 1
                if retry_count < max_retries:
                    logger.info(
                        f"Retrying connection in {retry_delay}s... "
                        f"({retry_count}/{max_retries})"
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                else:
                    logger.error(f"Max retries reached for {stream_key}")
                    break

            except Exception as e:
                logger.error(f"WebSocket error for {stream_key}: {e}")
                retry_count += 1
                if retry_count < max_retries:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    break

            finally:
                # 清理连接
                if stream_key in self.connections:
                    del self.connections[stream_key]

    async def unsubscribe(self, stream: str):
        """
        取消订阅

        Args:
            stream: stream名称
        """
        if stream in self.subscriptions:
            del self.subscriptions[stream]

        if stream in self.connections:
            await self.connections[stream].close()
            del self.connections[stream]

        logger.info(f"Unsubscribed from: {stream}")

    async def unsubscribe_all(self):
        """取消所有订阅"""
        for stream in list(self.connections.keys()):
            await self.unsubscribe(stream)

        logger.info("Unsubscribed from all streams")

    async def close(self):
        """关闭所有连接"""
        await self.unsubscribe_all()
        self.running = False

    # ==================== 便捷方法 ====================

    @staticmethod
    def transform_ticker(raw_data: Dict) -> Dict:
        """转换ticker数据为标准格式"""
        return {
            "symbol": raw_data.get("s"),
            "price": float(raw_data.get("c", 0)),
            "price_change": float(raw_data.get("p", 0)),
            "price_change_percent": float(raw_data.get("P", 0)),
            "high": float(raw_data.get("h", 0)),
            "low": float(raw_data.get("l", 0)),
            "volume": float(raw_data.get("v", 0)),
            "quote_volume": float(raw_data.get("q", 0)),
            "open_price": float(raw_data.get("o", 0)),
            "close_price": float(raw_data.get("c", 0)),
            "trades_count": int(raw_data.get("n", 0)),
            "event_time": raw_data.get("E"),
        }

    @staticmethod
    def transform_trade(raw_data: Dict) -> Dict:
        """转换trade数据为标准格式"""
        return {
            "symbol": raw_data.get("s"),
            "trade_id": raw_data.get("t"),
            "price": float(raw_data.get("p", 0)),
            "quantity": float(raw_data.get("q", 0)),
            "buyer_is_maker": raw_data.get("m"),
            "trade_time": raw_data.get("T"),
            "event_time": raw_data.get("E"),
        }

    @staticmethod
    def transform_depth(raw_data: Dict) -> Dict:
        """转换depth数据为标准格式"""
        return {
            "symbol": raw_data.get("s"),
            "first_update_id": raw_data.get("U"),
            "final_update_id": raw_data.get("u"),
            "bids": [[float(p), float(q)] for p, q in raw_data.get("b", [])],
            "asks": [[float(p), float(q)] for p, q in raw_data.get("a", [])],
            "event_time": raw_data.get("E"),
        }

    @staticmethod
    def transform_kline(raw_data: Dict) -> Dict:
        """转换kline数据为标准格式"""
        k = raw_data.get("k", {})
        return {
            "symbol": raw_data.get("s"),
            "interval": k.get("i"),
            "open_time": k.get("t"),
            "close_time": k.get("T"),
            "open": float(k.get("o", 0)),
            "high": float(k.get("h", 0)),
            "low": float(k.get("l", 0)),
            "close": float(k.get("c", 0)),
            "volume": float(k.get("v", 0)),
            "quote_volume": float(k.get("q", 0)),
            "trades_count": int(k.get("n", 0)),
            "is_closed": k.get("x"),
            "event_time": raw_data.get("E"),
        }


# ==================== 使用示例 ====================

async def example_usage():
    """使用示例"""
    ws = BinanceWebSocket()

    # 定义回调函数
    def on_ticker(data):
        ticker = BinanceWebSocket.transform_ticker(data)
        print(f"Ticker: {ticker['symbol']} @ {ticker['price']}")

    async def on_trade(data):
        trade = BinanceWebSocket.transform_trade(data)
        print(f"Trade: {trade['price']} x {trade['quantity']}")

    # 订阅
    await ws.subscribe_ticker("BTCUSDT", on_ticker)
    await ws.subscribe_trades("BTCUSDT", on_trade)

    # 运行30秒
    await asyncio.sleep(30)

    # 清理
    await ws.close()


if __name__ == "__main__":
    # 测试运行
    asyncio.run(example_usage())
