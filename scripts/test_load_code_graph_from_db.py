from src.storage.metadata import MetadataStore


def main() -> None:
    repo_id = input("Repo ID: ").strip()

    if not repo_id:
        raise ValueError("Repo ID is required")

    store = MetadataStore()
    graph = store.load_code_graph(repo_id)

    print("=" * 100)
    print(f"Loaded graph for repo_id={repo_id}")
    print("=" * 100)
    print(f"Nodes: {len(graph.nodes)}")
    print(f"Edges: {len(graph.edges)}")

    print("\nSample nodes:")
    for index, node in enumerate(graph.nodes.values()):
        if index >= 10:
            break

        print(
            f"- {node.qualified_name} | "
            f"{node.node_type} | "
            f"{node.relative_path}:{node.start_line}-{node.end_line}"
        )

    print("\nSample edges:")
    for index, edge in enumerate(graph.edges):
        if index >= 10:
            break

        source = graph.nodes.get(edge.source_id)
        target = graph.nodes.get(edge.target_id)

        source_name = source.qualified_name if source else edge.source_id
        target_name = target.qualified_name if target else edge.target_id

        print(f"- {source_name} --{edge.edge_type}--> {target_name}")

    print("\nTest callers of TaskService.create_task:")
    result = graph.find_callers("TaskService.create_task")

    targets = result.get("targets", [])
    callers = result.get("callers", [])

    print("Targets:")
    for node in targets:
        print(f"- {node.qualified_name} | {node.relative_path}:{node.start_line}-{node.end_line}")

    print("Callers:")
    for node in callers:
        print(f"- {node.qualified_name} | {node.relative_path}:{node.start_line}-{node.end_line}")


if __name__ == "__main__":
    main()