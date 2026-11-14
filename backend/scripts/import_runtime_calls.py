"""Import a local runtime report matching the indexed repository version."""

import argparse
import json
from pathlib import Path

from src.graph.runtime_trace import apply_runtime_report
from src.storage.metadata import MetadataStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo_id")
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    if args.report.stat().st_size > 20 * 1024 * 1024:
        parser.error("Runtime report exceeds 20 MB")
    report = json.loads(args.report.read_text(encoding="utf-8"))
    store = MetadataStore()
    graph = store.load_code_graph(args.repo_id)
    result = apply_runtime_report(graph, report, store.load_files(args.repo_id))
    if result["imported"]:
        store.save_graph_analysis(args.repo_id, graph)
    print(json.dumps(result))
    print("Reload the repository session to use this evidence in chat.")


if __name__ == "__main__":
    main()
