from src.agent.graph import AgentGraph
from src.agent.query_router import QueryPlan


class FakeRouter:
    def __init__(self, query_type, symbol):
        self.query_type = query_type
        self.symbol = symbol

    def route(self, question):
        return QueryPlan(
            query_type=self.query_type,
            symbol=self.symbol,
            rewritten_query=question,
            confidence=1.0,
            reason="test",
            router="test",
        )


class FakeTools:
    def __init__(self, references=None, callees=None):
        self.references = references or []
        self.callees = callees or []

    def find_references(self, symbol):
        return self.references

    def find_callees(self, symbol):
        return {"sources": [], "callees": self.callees}

    def impact_analysis(self, symbol):
        return {"targets": [], "affected": []}

    def find_symbol(self, symbol):
        return []

    def search_code(self, query, top_k=5):
        return []


def test_graph_answer_uses_graph_sources_for_citations():
    tools = FakeTools(
        callees=[
            {
                "relative_path": "service.py",
                "start_line": 10,
                "end_line": 12,
                "symbol_type": "function",
                "qualified_name": "validate_email",
                "line_number": 10,
                "line": "function validate_email",
                "is_definition": False,
            }
        ]
    )
    agent = AgentGraph(
        tools=tools,
        retriever=None,
        query_router=FakeRouter("callee_query", "UserService.create_user"),
    )

    response = agent.invoke("what does UserService.create_user call")

    assert response.citations == ["service.py:10-12 (function: validate_email)"]
    assert response.raw_results["router"] == "test"


def test_definition_only_reference_is_not_reported_as_caller():
    tools = FakeTools(
        references=[
            {
                "relative_path": "service.py",
                "start_line": 5,
                "end_line": 5,
                "line_number": 5,
                "line": "class User:",
                "is_definition": True,
            }
        ]
    )
    agent = AgentGraph(
        tools=tools,
        retriever=None,
        query_router=FakeRouter("caller_query", "User"),
    )

    response = agent.invoke("who calls User")

    assert "defined, but no callers/references were found" in response.answer
