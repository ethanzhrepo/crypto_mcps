from src.core.models import CryptoOverviewInput, DerivativesHubInput, MarketMicrostructureInput


def _enum_from_items_ref(schema: dict, *, prop: str) -> list:
    inc = schema["properties"][prop]
    items = inc["items"]
    ref = items["$ref"]
    name = ref.split("/")[-1]
    return schema["$defs"][name]["enum"]


def test_crypto_overview_include_fields_enum_exposed():
    schema = CryptoOverviewInput.model_json_schema()
    enum = _enum_from_items_ref(schema, prop="include_fields")
    assert set(enum) == {
        "all",
        "basic",
        "market",
        "supply",
        "holders",
        "social",
        "sector",
        "dev_activity",
    }


def test_market_microstructure_include_fields_enum_exposed():
    schema = MarketMicrostructureInput.model_json_schema()
    enum = _enum_from_items_ref(schema, prop="include_fields")
    assert "ticker" in enum
    assert "orderbook" in enum
    assert "all" in enum


def test_derivatives_hub_include_fields_enum_exposed():
    schema = DerivativesHubInput.model_json_schema()
    enum = _enum_from_items_ref(schema, prop="include_fields")
    assert "funding_rate" in enum
    assert "open_interest" in enum
    assert "all" in enum

