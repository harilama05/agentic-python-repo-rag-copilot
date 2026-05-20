from src.storage.metadata import MetadataStore


def main() -> None:
    store = MetadataStore()
    repos = store.list_repositories()

    print("=" * 100)
    print("Repositories")
    print("=" * 100)

    if not repos:
        print("No repositories found.")
        return

    for repo in repos:
        repo_id = repo["repo_id"]

        chunk_count = store.count_chunks(repo_id)
        node_count = store.count_code_nodes(repo_id)
        edge_count = store.count_code_edges(repo_id)

        print(
            f"{repo_id} | "
            f"name={repo['name']} | "
            f"source={repo['source_type']} | "
            f"persistent={repo['is_persistent']} | "
            f"status={repo['status']} | "
            f"chunks={repo['chunk_count']} "
            f"(stored={chunk_count}) | "
            f"nodes={node_count} | "
            f"edges={edge_count}"
        )


if __name__ == "__main__":
    main()