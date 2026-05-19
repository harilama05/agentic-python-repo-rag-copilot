from src.agent.query_router import (
    LLMQueryRouter,
    extract_json_object,
    is_valid_code_symbol,
    rule_based_fallback_route,
)


def test_extract_json_object_handles_markdown_fence():
    data = extract_json_object(
        """```json
{"query_type": "caller_query", "symbol": "UserService", "confidence": 0.9}
```"""
    )

    assert data["query_type"] == "caller_query"
    assert data["symbol"] == "UserService"


def test_symbol_validation_accepts_common_python_symbols():
    assert is_valid_code_symbol("create_user")
    assert is_valid_code_symbol("User")
    assert is_valid_code_symbol("UserService.create_user")
    assert not is_valid_code_symbol("user")


def test_rule_based_fallback_route_keeps_existing_behavior():
    plan = rule_based_fallback_route("what does UserService.create_user call")

    assert plan.query_type == "callee_query"
    assert plan.symbol == "UserService.create_user"
    assert plan.router == "fallback_rule"


def test_llm_router_without_api_key_uses_fallback(monkeypatch):
    monkeypatch.setattr("src.agent.query_router.settings.openai_api_key", None)

    plan = LLMQueryRouter(api_key=None).route("who calls User")

    assert plan.query_type == "reference_query"
    assert plan.symbol == "User"
    assert plan.router == "fallback_rule"
