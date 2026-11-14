"""Refresh graph evidence from DB snapshots without embedding or executing code."""

import argparse

from src.graph.static_analysis import build_from_sources
from src.storage.metadata import MetadataStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo_id")
    args = parser.parse_args()
    store = MetadataStore()
    sources = store.load_files(args.repo_id)
    if not sources:
        parser.error("No indexed source snapshots; index the repository first")
    graph = build_from_sources(sources)
    store.replace_code_graph(repo_id=args.repo_id, code_graph=graph)
    print(f"Graph refreshed: {len(graph.nodes)} nodes, {len(graph.edges)} edges, "
          f"{len(graph.unresolved_calls)} unresolved calls. Previous runtime evidence was cleared.")


if __name__ == "__main__":
    main()
