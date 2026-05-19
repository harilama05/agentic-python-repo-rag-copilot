from pathlib import Path

from src.graph.code_graph import build_code_graph
def test_code_graph_builds_calls_and_contains_edges():
    repo_path = Path("data/repos/sample_python_repo")

    graph = build_code_graph(repo_path)

    assert graph.find_nodes("UserService.create_user")

    user_service = graph.find_nodes("UserService")[0]
    create_user = graph.find_nodes("UserService.create_user")[0]

    assert any(
        edge.source_id == user_service.node_id
        and edge.target_id == create_user.node_id
        and edge.edge_type == "contains"
        for edge in graph.edges
    )

    callees = graph.find_callees("UserService.create_user")["callees"]
    callee_names = {node.qualified_name for node in callees}

    assert "User" in callee_names

    affected = graph.impact_analysis("User")["affected"]
    affected_names = {node.qualified_name for node in affected}
    assert "UserService.create_user" in affected_names
