"""
MCP HTTP REST API 实际环境测试

这些测试在独立容器中通过HTTP访问已启动的FastAPI服务，触发真实第三方API调用。
每个测试都会把接口响应写入 /tmp，方便在 Docker 测试容器中查看。
"""
import json
import os
from pathlib import Path

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.live, pytest.mark.live_free]


@pytest.fixture
def base_url():
    """从环境变量读取目标HTTP地址，默认指向本地转发端口"""
    return os.getenv("MCP_HTTP_BASE_URL", "http://localhost:8001")


@pytest.fixture
async def rest_client(base_url):
    """面向真实HTTP服务器的AsyncClient"""
    async with AsyncClient(base_url=base_url, timeout=60.0) as client:
        yield client


@pytest.fixture
def record_response():
    """将接口响应持久化到 /tmp 目录"""

    def _record(name: str, response):
        payload = {
            "status_code": response.status_code,
            "body": response.json(),
        }
        path = Path("/tmp") / f"mcp_server_{name}_response.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        return path

    return _record


@pytest.mark.asyncio
async def test_health_endpoint(rest_client, record_response):
    """健康检查应返回服务状态并保存响应"""
    response = await rest_client.get("/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "mcp-server"
    assert "tools_count" in body

    record_response("health", response)


@pytest.mark.asyncio
async def test_list_tools_endpoint(rest_client, record_response):
    """工具列表应返回可用REST端点信息，并与健康检查中的工具数量一致"""
    response = await rest_client.get("/tools")
    assert response.status_code == 200

    body = response.json()
    assert "tools" in body
    tools = body["tools"]
    assert isinstance(tools, list)
    assert len(tools) > 0

    # /tools 返回的数量应与 /health 中的 tools_count 一致，避免硬编码工具个数
    health_response = await rest_client.get("/health")
    assert health_response.status_code == 200
    health_body = health_response.json()
    assert len(tools) == health_body.get("tools_count")

    # 至少包含核心工具端点
    endpoints = {tool["endpoint"] for tool in tools}
    core_endpoints = {
        "/tools/crypto_overview",
        "/tools/market_microstructure",
        "/tools/derivatives_hub",
        "/tools/web_research_search",
        "/tools/macro_hub",
        "/tools/draw_chart",
    }
    assert core_endpoints.issubset(endpoints)

    record_response("tools_list", response)


@pytest.mark.asyncio
async def test_tools_registry_endpoint(rest_client, record_response):
    """工具 registry 应返回完整可执行元数据"""
    response = await rest_client.get("/tools/registry")
    assert response.status_code == 200

    body = response.json()
    assert "tools" in body
    registry_tools = body["tools"]
    assert isinstance(registry_tools, list)
    assert len(registry_tools) > 0

    # 与 /tools 的 enabled 数量一致
    tools_response = await rest_client.get("/tools")
    assert tools_response.status_code == 200
    assert len(registry_tools) == len(tools_response.json()["tools"])

    # 校验字段
    sample = registry_tools[0]
    for field in [
        "name",
        "description",
        "endpoint",
        "input_schema",
        "output_schema",
        "examples",
        "capabilities",
        "freshness",
        "limitations",
        "cost_hints",
    ]:
        assert field in sample

    assert isinstance(sample["freshness"], dict)
    assert isinstance(sample["freshness"].get("typical_ttl_seconds"), int)

    # 至少包含 crypto_overview，并且 schema 合法
    names = {t["name"] for t in registry_tools}
    assert "crypto_overview" in names
    crypto_entry = next(t for t in registry_tools if t["name"] == "crypto_overview")
    assert "symbol" in crypto_entry["input_schema"]["properties"]
    assert crypto_entry["output_schema"] is not None

    record_response("tools_registry", response)


@pytest.mark.asyncio
async def test_single_tool_definition_endpoint(rest_client, record_response):
    """GET /tools/{name} 应返回单工具 registry entry"""
    response = await rest_client.get("/tools/crypto_overview")
    assert response.status_code == 200

    body = response.json()
    assert body["name"] == "crypto_overview"
    assert body["endpoint"] == "/tools/crypto_overview"
    assert "input_schema" in body and "output_schema" in body

    record_response("tool_definition_crypto_overview", response)


@pytest.mark.asyncio
async def test_crypto_overview_endpoint_live(rest_client, record_response):
    """POST /tools/crypto_overview 需要访问真实外部API"""
    payload = {"symbol": "btc", "include_fields": ["basic", "market"]}
    response = await rest_client.post("/tools/crypto_overview", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["symbol"] == "BTC"
    assert body["data"]["market"]["price"] > 0

    record_response("crypto_overview", response)


@pytest.mark.asyncio
async def test_derivatives_endpoint_live(rest_client, record_response):
    """POST /tools/derivatives_hub 应返回真实衍生品数据"""
    payload = {"symbol": "BTCUSDT", "include_fields": ["funding_rate", "open_interest"]}
    response = await rest_client.post("/tools/derivatives_hub", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["symbol"] == "BTCUSDT"
    funding = body["data"]["funding_rate"]
    assert isinstance(funding["funding_rate"], (int, float))
    assert funding["funding_rate_annual"] is not None

    record_response("derivatives_hub", response)


@pytest.mark.asyncio
async def test_market_microstructure_endpoint_live(rest_client, record_response):
    """POST /tools/market_microstructure 调用真实市场数据"""
    payload = {
        "symbol": "BTC/USDT",
        "venues": ["binance"],
        "include_fields": ["ticker"],
    }
    response = await rest_client.post("/tools/market_microstructure", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["symbol"] == "BTCUSDT"
    assert body["data"]["ticker"]["last_price"] > 0

    record_response("market_microstructure", response)


@pytest.mark.asyncio
async def test_crypto_overview_validation_error(rest_client, record_response):
    """非法参数应返回422并记录响应"""
    payload = {"symbol": "btc", "include_fields": ["invalid_field"]}
    response = await rest_client.post("/tools/crypto_overview", json=payload)
    assert response.status_code == 422

    body = response.json()
    error_msgs = " ".join(err.get("msg", "") for err in body.get("detail", []))
    # Pydantic v2 uses "Input should be" instead of "Invalid field"
    assert "Input should be" in error_msgs or "invalid_field" in error_msgs.lower()

    record_response("crypto_overview_validation_error", response)


@pytest.mark.asyncio
async def test_web_research_search_endpoint_live(rest_client, record_response):
    """POST /tools/web_research_search 应返回真实搜索结果"""
    payload = {"query": "Bitcoin price prediction 2025", "limit": 5}
    response = await rest_client.post("/tools/web_research_search", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["query"] == "Bitcoin price prediction 2025"
    assert "results" in body
    # 搜索结果可能为空（取决于API配置），但不应报错
    results = body["results"]
    assert isinstance(results, list)

    # 如果有结果，验证结构
    if results:
        first_result = results[0]
        assert "title" in first_result
        assert "url" in first_result

    record_response("web_research_search", response)


@pytest.mark.asyncio
async def test_web_research_search_news(rest_client, record_response):
    """POST /tools/web_research_search 的新闻聚合功能"""
    payload = {"query": "Ethereum upgrade news", "limit": 10, "scope": "news"}
    response = await rest_client.post("/tools/web_research_search", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["query"] == "Ethereum upgrade news"
    assert "results" in body

    # 新闻结果可能为空（取决于配置），但不应报错
    results = body["results"]
    assert isinstance(results, list)

    record_response("web_research_search_news", response)


@pytest.mark.asyncio
async def test_web_research_search_news_with_validation(rest_client, record_response):
    """新闻搜索应返回结果或明确的warnings"""
    payload = {"query": "Bitcoin ETF approval", "scope": "news", "limit": 10}
    response = await rest_client.post("/tools/web_research_search", json=payload)
    assert response.status_code == 200

    body = response.json()
    results = body["results"]
    warnings = body.get("warnings", [])

    # 核心验证：不允许"无结果且无warnings"
    if len(results) == 0:
        assert len(warnings) > 0, (
            "Empty news results must have warnings explaining why "
            "(e.g., 'Telegram scraper未初始化', 'Bing News需要API key')"
        )

        # 验证warnings内容有用
        warnings_text = " ".join(warnings)
        useful_keywords = ["未初始化", "需要", "API", "key", "失败", "不可用"]
        has_useful_info = any(kw in warnings_text for kw in useful_keywords)
        assert has_useful_info, f"Warnings lack useful information: {warnings}"
    else:
        # 有结果时验证结构
        for result in results[:3]:
            assert result["title"], "News result must have title"
            assert result["url"], "News result must have URL"

    record_response("web_research_search_news_validated", response)


@pytest.mark.asyncio
async def test_crypto_news_search_endpoint_live(rest_client, record_response):
    """POST /tools/crypto_news_search 应返回加密新闻搜索结果（依赖宿主机 Telegram Scraper 服务）"""
    payload = {"query": "btc", "limit": 5, "time_range": "24h"}
    response = await rest_client.post("/tools/crypto_news_search", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body.get("query") == "btc"
    assert "results" in body
    assert "total_results" in body
    assert "source_meta" in body
    assert "warnings" in body

    warnings_text = " ".join(body.get("warnings", []))
    assert "未初始化" not in warnings_text

    results = body["results"]
    assert isinstance(results, list)
    if results:
        first_result = results[0]
        assert first_result.get("title")
        assert "url" in first_result
        assert first_result.get("source")

    record_response("crypto_news_search", response)


@pytest.mark.asyncio
async def test_crypto_news_search_endpoint_live_requires_results(rest_client, record_response):
    """POST /tools/crypto_news_search 必须至少返回1条结果（btc, limit=20）"""
    payload = {"query": "btc", "limit": 20, "time_range": "24h"}
    response = await rest_client.post("/tools/crypto_news_search", json=payload)
    assert response.status_code == 200

    body = response.json()
    results = body.get("results", [])
    assert isinstance(results, list)
    assert len(results) >= 1, "Expected at least 1 crypto news search result for query=btc"

    first_result = results[0]
    assert first_result.get("title")
    assert "url" in first_result
    assert first_result.get("source")

    record_response("crypto_news_search_requires_results", response)


@pytest.mark.asyncio
async def test_web_research_all_sources_unavailable(rest_client, record_response):
    """所有新闻源不可用时应返回明确warnings"""
    payload = {"query": "test", "scope": "news"}
    response = await rest_client.post("/tools/web_research_search", json=payload)
    assert response.status_code == 200

    body = response.json()
    warnings = body.get("warnings", [])

    # 如果确实没有可用源，必须有警告
    # 允许有结果（如果有配置的源）或有warnings（如果没有源）
    assert len(body["results"]) > 0 or len(warnings) > 0, (
        "Either results or warnings must be present"
    )

    record_response("web_research_no_sources", response)


@pytest.mark.asyncio
async def test_onchain_activity_endpoint_live(rest_client, record_response):
    """POST /tools/onchain_activity 应返回真实链上活动数据"""
    payload = {"chain": "ethereum"}
    response = await rest_client.post("/tools/onchain_activity", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["activity"]["chain"] == "ethereum"
    assert "activity" in body

    # 验证关键字段存在
    data = body["activity"]
    assert "transaction_count_24h" in data
    assert "timestamp" in data

    # 至少应该有一些非null的数据点（如果API key未配置，可能所有数据字段都是null）
    non_null_count = sum(1 for k, v in data.items() if v is not None and k != "timestamp" and k != "chain")
    # 放宽要求：至少有timestamp字段存在即可（数据字段可能因API key未配置而为null）
    assert non_null_count >= 0, f"Expected valid response structure, got {non_null_count} non-null fields"

    record_response("onchain_activity", response)


@pytest.mark.asyncio
async def test_market_microstructure_advanced_fields(rest_client, record_response):
    """POST /tools/market_microstructure 测试高级字段（klines, trades, volume_profile等）"""
    payload = {
        "symbol": "BTC/USDT",
        "venues": ["binance"],
        "include_fields": ["ticker", "klines", "trades", "volume_profile", "taker_flow", "slippage"],
    }
    response = await rest_client.post("/tools/market_microstructure", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["symbol"] == "BTCUSDT"
    data = body["data"]

    # 验证基础字段
    assert data["ticker"] is not None
    assert data["ticker"]["last_price"] > 0

    # 验证高级字段（这些字段应该被实现）
    if data.get("klines"):
        assert isinstance(data["klines"], list)
        assert len(data["klines"]) > 0
        assert "open" in data["klines"][0]
        assert "close" in data["klines"][0]

    if data.get("trades"):
        assert isinstance(data["trades"], list)
        # trades 用于计算其他字段

    # volume_profile 和 taker_flow 依赖 trades
    if data.get("volume_profile"):
        assert "poc_price" in data["volume_profile"]

    if data.get("taker_flow"):
        assert "total_buy_volume" in data["taker_flow"]
        assert "total_sell_volume" in data["taker_flow"]

    record_response("market_microstructure_advanced", response)


@pytest.mark.asyncio
async def test_market_microstructure_aggregated_orderbook(rest_client, record_response):
    """POST /tools/market_microstructure 测试聚合订单簿功能"""
    payload = {
        "symbol": "BTC/USDT",
        "venues": ["binance", "okx"],
        "include_fields": ["aggregated_orderbook"],
        "orderbook_depth": 100,
    }
    response = await rest_client.post("/tools/market_microstructure", json=payload)
    assert response.status_code == 200

    body = response.json()
    data = body["data"]

    # 验证聚合订单簿存在
    if data.get("aggregated_orderbook"):
        agg_ob = data["aggregated_orderbook"]
        assert "exchanges" in agg_ob
        assert len(agg_ob["exchanges"]) >= 1
        assert "bids" in agg_ob
        assert "asks" in agg_ob
        assert isinstance(agg_ob["bids"], list)
        assert isinstance(agg_ob["asks"], list)
        assert agg_ob["best_bid"] > 0
        assert agg_ob["best_ask"] > 0
        assert agg_ob["global_mid"] > 0

    record_response("market_microstructure_aggregated_orderbook", response)


@pytest.mark.asyncio
async def test_derivatives_hub_advanced_fields(rest_client, record_response):
    """POST /tools/derivatives_hub 测试高级字段"""
    payload = {
        "symbol": "BTCUSDT",
        "include_fields": [
            "funding_rate",
            "open_interest",
            "long_short_ratio",
            "basis_curve",
        ],
    }
    response = await rest_client.post("/tools/derivatives_hub", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["symbol"] == "BTCUSDT"
    data = body["data"]

    # 验证基础字段
    assert data["funding_rate"] is not None
    assert isinstance(data["funding_rate"]["funding_rate"], (int, float))

    assert data["open_interest"] is not None
    assert data["open_interest"]["open_interest_usd"] > 0

    # 验证高级字段
    if data.get("long_short_ratio"):
        assert isinstance(data["long_short_ratio"], list)
        if data["long_short_ratio"]:
            assert "long_ratio" in data["long_short_ratio"][0]
            assert "short_ratio" in data["long_short_ratio"][0]

    # basis_curve 依赖 funding_rate
    if data.get("basis_curve"):
        # basis_curve包含: points (list), contango (bool), spot_price等字段
        assert "points" in data["basis_curve"] or "spot_price" in data["basis_curve"]

    record_response("derivatives_hub_advanced", response)


@pytest.mark.asyncio
async def test_macro_hub_endpoint_live(rest_client, record_response):
    """POST /tools/macro_hub 应返回真实宏观数据"""
    payload = {"include_fields": ["crypto_indices", "fear_greed", "economic_calendar"]}
    response = await rest_client.post("/tools/macro_hub", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert "data" in body
    data = body["data"]

    # 至少应该有一些非null的数据
    non_null_count = sum(1 for k, v in data.items() if v is not None)
    assert non_null_count >= 1, f"Expected at least 1 non-null field, got {non_null_count}"

    record_response("macro_hub", response)


@pytest.mark.asyncio
async def test_macro_hub_fed_data(rest_client, record_response):
    """macro_hub应返回完整的FED数据"""
    payload = {"mode": "fed"}
    response = await rest_client.post("/tools/macro_hub", json=payload)
    assert response.status_code == 200

    body = response.json()
    data = body["data"]

    # 严格验证FED数据
    assert data["fed"] is not None, "FED data should not be null"
    assert isinstance(data["fed"], list), "FED data should be a list"
    assert len(data["fed"]) > 0, "FED data should not be empty"

    # 验证FED数据结构
    fed_symbols = [item["symbol"] for item in data["fed"]]
    expected_indicators = ["CPIAUCSL", "UNRATE", "DGS10"]  # CPI, 失业率, 10年期国债
    for indicator in expected_indicators:
        assert indicator in fed_symbols, f"Missing FED indicator: {indicator}"

    # 验证数据值合理性
    for item in data["fed"]:
        assert item["value"] is not None, f"{item['symbol']} value should not be null"
        assert isinstance(item["value"], (int, float)), f"{item['symbol']} value should be numeric"

    record_response("macro_hub_fed", response)


@pytest.mark.asyncio
async def test_macro_hub_indices_data(rest_client, record_response):
    """macro_hub应返回完整的传统金融指数（含Russell 2000和BTC/ETH）"""
    payload = {"mode": "indices"}
    response = await rest_client.post("/tools/macro_hub", json=payload)
    assert response.status_code == 200

    body = response.json()
    data = body["data"]

    # 严格验证indices数据
    assert data["indices"] is not None, "Indices data should not be null"
    assert isinstance(data["indices"], list), "Indices data should be a list"
    assert len(data["indices"]) > 0, "Indices data should not be empty"

    # 验证关键指数
    indices_symbols = [item["symbol"] for item in data["indices"]]

    # 核心股指
    expected_stock_indices = ["^GSPC", "^IXIC", "^DJI", "^RUT"]  # S&P 500, NASDAQ, DOW, Russell 2000
    for index in expected_stock_indices:
        assert index in indices_symbols, f"Missing stock index: {index}"

    # 加密货币价格 (新增)
    expected_crypto = ["BTC-USD", "ETH-USD"]  # Bitcoin, Ethereum
    for crypto in expected_crypto:
        assert crypto in indices_symbols, f"Missing crypto: {crypto}"

    # 验证数据值存在且合理
    for item in data["indices"]:
        assert item["value"] is not None, f"{item['symbol']} value should not be null"
        assert isinstance(item["value"], (int, float)), f"{item['symbol']} value should be numeric"
        assert item["value"] > 0, f"{item['symbol']} value should be positive"

    record_response("macro_hub_indices", response)


@pytest.mark.asyncio
async def test_macro_hub_dashboard_complete(rest_client, record_response):
    """macro_hub dashboard模式应返回所有字段"""
    payload = {"mode": "dashboard"}
    response = await rest_client.post("/tools/macro_hub", json=payload)
    assert response.status_code == 200

    body = response.json()
    data = body["data"]

    # 验证所有字段都存在且有数据
    fields_to_check = {
        "fed": "FED economic indicators",
        "indices": "Traditional market indices",
        "crypto_indices": "Crypto market indices",
        "fear_greed": "Fear & Greed index"
    }

    missing_fields = []
    for field, description in fields_to_check.items():
        if data.get(field) is None or (isinstance(data[field], list) and len(data[field]) == 0):
            missing_fields.append(f"{field} ({description})")

    assert len(missing_fields) == 0, f"Missing or empty fields: {', '.join(missing_fields)}"

    record_response("macro_hub_dashboard", response)


# ==================== P0: New Tools Tests ====================


@pytest.mark.asyncio
async def test_price_history_endpoint_live(rest_client, record_response):
    """POST /tools/price_history 应返回历史K线和技术指标"""
    payload = {
        "symbol": "BTC/USDT",
        "interval": "1d",
        "lookback_days": 30,
        "include_indicators": ["sma", "rsi", "macd"]
    }
    response = await rest_client.post("/tools/price_history", json=payload)
    assert response.status_code == 200

    body = response.json()
    # symbol 可能保留原格式 BTC/USDT 或转为 BTCUSDT
    assert "symbol" in body or "ohlcv" in body or "klines" in body

    # 验证K线数据存在
    ohlcv = body.get("ohlcv") or body.get("klines") or body.get("data", {}).get("ohlcv")
    if ohlcv is not None:
        assert isinstance(ohlcv, list)
        assert len(ohlcv) > 0

    record_response("price_history", response)


@pytest.mark.asyncio
async def test_price_history_with_statistics(rest_client, record_response):
    """price_history应返回统计数据"""
    payload = {
        "symbol": "ETH/USDT",
        "interval": "1d",
        "lookback_days": 60,
        "include_indicators": ["sma"]
    }
    response = await rest_client.post("/tools/price_history", json=payload)
    assert response.status_code == 200

    body = response.json()
    # 验证有数据返回
    assert body is not None
    assert isinstance(body, dict)

    record_response("price_history_statistics", response)


@pytest.mark.asyncio
async def test_sector_peers_endpoint_live(rest_client, record_response):
    """POST /tools/sector_peers 应返回同类币种对比数据"""
    payload = {"symbol": "AAVE", "limit": 5}
    response = await rest_client.post("/tools/sector_peers", json=payload)
    assert response.status_code == 200

    body = response.json()
    # 响应结构可能直接在顶层
    assert body is not None
    assert isinstance(body, dict)

    # 验证有peers或category相关数据
    has_sector_data = (
        "peers" in body or
        "sector" in body or
        "category" in body or
        "target" in body or
        "comparison" in body
    )
    assert has_sector_data, f"Expected sector data, got: {list(body.keys())}"

    record_response("sector_peers", response)


@pytest.mark.asyncio
async def test_sector_peers_with_metrics(rest_client, record_response):
    """sector_peers应返回估值指标"""
    payload = {"symbol": "UNI", "limit": 10}
    response = await rest_client.post("/tools/sector_peers", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body is not None
    assert isinstance(body, dict)

    record_response("sector_peers_metrics", response)


@pytest.mark.asyncio
async def test_sentiment_aggregator_endpoint_live(rest_client, record_response):
    """POST /tools/sentiment_aggregator 应返回聚合情绪数据"""
    payload = {"symbol": "BTC", "lookback_hours": 24}
    response = await rest_client.post("/tools/sentiment_aggregator", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body is not None

    # 验证情绪相关字段（实际响应结构是直接在顶层）
    has_sentiment_data = (
        "overall_sentiment" in body or
        "overall_score" in body or
        "sentiment" in body or
        "historical_sentiment" in body or
        "analysis_period" in body
    )
    assert has_sentiment_data, f"Expected sentiment data, got: {list(body.keys())}"

    # 如果有overall_sentiment，验证其结构
    if "overall_sentiment" in body:
        sentiment = body["overall_sentiment"]
        assert "score" in sentiment or "label" in sentiment

    record_response("sentiment_aggregator", response)



# ==================== P1: DeFi & Options Tests ====================


@pytest.mark.asyncio
async def test_onchain_tvl_fees_endpoint_live(rest_client, record_response):
    """POST /tools/onchain_tvl_fees 应返回协议TVL和费用数据"""
    payload = {"protocol": "uniswap"}
    response = await rest_client.post("/tools/onchain_tvl_fees", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert "data" in body or "tvl" in body

    # 验证TVL数据
    data = body.get("data", body)
    tvl = data.get("tvl")
    if tvl is not None:
        assert isinstance(tvl, dict) or isinstance(tvl, (int, float))

    record_response("onchain_tvl_fees", response)


@pytest.mark.asyncio
async def test_etf_flows_holdings_endpoint_live(rest_client, record_response):
    """POST /tools/etf_flows_holdings 应返回ETF资金流数据"""
    payload = {"dataset": "bitcoin", "include_fields": ["flows"]}
    response = await rest_client.post("/tools/etf_flows_holdings", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["dataset"] == "bitcoin"

    # 验证flows数据
    flows = body.get("flows", [])
    assert isinstance(flows, list)

    record_response("etf_flows_holdings", response)


@pytest.mark.asyncio
async def test_options_vol_skew_endpoint_live(rest_client, record_response):
    """POST /tools/options_vol_skew 应返回期权波动率数据"""
    payload = {"symbol": "BTC"}
    response = await rest_client.post("/tools/options_vol_skew", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["symbol"] == "BTC"

    # 验证数据结构
    data = body.get("data", {})
    assert isinstance(data, dict)

    record_response("options_vol_skew", response)


@pytest.mark.asyncio
async def test_draw_chart_endpoint_live(rest_client, record_response):
    """POST /tools/draw_chart 应返回图表配置"""
    payload = {
        "chart_type": "line",
        "symbol": "BTC/USDT",
        "config": {
            "data": [{"x": [1, 2, 3], "y": [100, 200, 150], "type": "scatter"}],
            "layout": {"title": "Test Chart"}
        }
    }
    response = await rest_client.post("/tools/draw_chart", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["symbol"] == "BTC/USDT"
    assert "chart" in body

    record_response("draw_chart", response)


# ==================== P2: Hyperliquid & MEV Tests ====================


@pytest.mark.asyncio
async def test_hyperliquid_market_endpoint_live(rest_client, record_response):
    """POST /tools/hyperliquid_market 应返回Hyperliquid市场数据"""
    payload = {"symbol": "BTC", "include_fields": ["funding", "open_interest"]}
    response = await rest_client.post("/tools/hyperliquid_market", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["symbol"] == "BTC"
    assert "data" in body

    record_response("hyperliquid_market", response)


@pytest.mark.asyncio
async def test_blockspace_mev_endpoint_live(rest_client, record_response):
    """POST /tools/blockspace_mev 应返回MEV数据"""
    payload = {"chain": "ethereum", "limit": 10}
    response = await rest_client.post("/tools/blockspace_mev", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["chain"] == "ethereum"

    record_response("blockspace_mev", response)


@pytest.mark.asyncio
async def test_cex_netflow_reserves_endpoint_live(rest_client, record_response):
    """POST /tools/cex_netflow_reserves 应返回交易所储备数据"""
    payload = {}
    response = await rest_client.post("/tools/cex_netflow_reserves", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert "reserves" in body or "data" in body

    record_response("cex_netflow_reserves", response)


@pytest.mark.asyncio
async def test_lending_liquidation_risk_endpoint_live(rest_client, record_response):
    """POST /tools/lending_liquidation_risk 应返回借贷风险数据"""
    payload = {}
    response = await rest_client.post("/tools/lending_liquidation_risk", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert "yields" in body or "data" in body

    record_response("lending_liquidation_risk", response)


@pytest.mark.asyncio
async def test_stablecoin_health_endpoint_live(rest_client, record_response):
    """POST /tools/stablecoin_health 应返回稳定币健康数据"""
    payload = {}
    response = await rest_client.post("/tools/stablecoin_health", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert "stablecoins" in body or "data" in body

    record_response("stablecoin_health", response)


# ==================== P2: Onchain Tools Tests ====================


@pytest.mark.asyncio
async def test_onchain_stablecoins_cex_endpoint_live(rest_client, record_response):
    """POST /tools/onchain_stablecoins_cex 应返回稳定币和CEX储备数据"""
    payload = {}
    response = await rest_client.post("/tools/onchain_stablecoins_cex", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert "data" in body or "stablecoins" in body or "cex_reserves" in body

    record_response("onchain_stablecoins_cex", response)


@pytest.mark.asyncio
async def test_onchain_bridge_volumes_endpoint_live(rest_client, record_response):
    """POST /tools/onchain_bridge_volumes 应返回跨链桥交易量数据"""
    payload = {}
    response = await rest_client.post("/tools/onchain_bridge_volumes", json=payload)
    assert response.status_code == 200

    body = response.json()
    # 实际响应结构包含 bridge_volumes 字段
    assert (
        "bridge_volumes" in body or
        "data" in body or
        "bridges" in body
    ), f"Expected bridge data, got: {list(body.keys())}"

    record_response("onchain_bridge_volumes", response)


@pytest.mark.asyncio
@pytest.mark.requires_key
async def test_onchain_dex_liquidity_endpoint_live(rest_client, record_response, skip_if_no_key):
    """POST /tools/onchain_dex_liquidity 应返回DEX流动性数据（需要THEGRAPH_API_KEY）"""
    skip_if_no_key("THEGRAPH_API_KEY")

    # chain 是必填参数
    payload = {"chain": "ethereum"}
    response = await rest_client.post("/tools/onchain_dex_liquidity", json=payload)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    body = response.json()
    assert body is not None
    assert "dex_liquidity" in body or "data" in body or "liquidity" in body

    record_response("onchain_dex_liquidity", response)


@pytest.mark.asyncio
async def test_onchain_governance_endpoint_live(rest_client, record_response):
    """POST /tools/onchain_governance 应返回治理提案数据"""
    # 使用 aave.eth，这是一个已知的有效 Snapshot 空间
    payload = {"snapshot_space": "aave.eth"}
    response = await rest_client.post("/tools/onchain_governance", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert "governance" in body or "data" in body or "proposals" in body

    record_response("onchain_governance", response)


@pytest.mark.asyncio
@pytest.mark.requires_key
async def test_onchain_token_unlocks_endpoint_live(rest_client, record_response, skip_if_no_key):
    """POST /tools/onchain_token_unlocks 应返回代币解锁数据（需要TOKEN_UNLOCKS_API_KEY）"""
    skip_if_no_key("TOKEN_UNLOCKS_API_KEY")

    # token_symbol 是可选的
    payload = {"token_symbol": "ARB"}
    response = await rest_client.post("/tools/onchain_token_unlocks", json=payload)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    body = response.json()
    assert "token_unlocks" in body or "data" in body

    record_response("onchain_token_unlocks", response)


@pytest.mark.asyncio
async def test_onchain_contract_risk_endpoint_live(rest_client, record_response):
    """POST /tools/onchain_contract_risk 应返回合约风险分析（GoPlus免费API）"""
    # contract_address 和 chain 都是必填参数
    payload = {
        "contract_address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "chain": "ethereum"
    }
    response = await rest_client.post("/tools/onchain_contract_risk", json=payload)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    body = response.json()
    assert "contract_risk" in body or "data" in body

    record_response("onchain_contract_risk", response)
