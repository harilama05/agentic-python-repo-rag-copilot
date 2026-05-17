from collections import defaultdict
from pathlib import Path

from src.evaluator import (
    evaluate_response,
    load_eval_cases,
    summarize_eval_results,
)
from src.indexer import build_codebase_agent

from src.settings import RETRIEVAL_MODE_FAST

def resolve_repo_path(repo_path: str) -> Path:
    path = Path(repo_path)

    if path.exists():
        return path

    # Fallback for older local setup if sample repo still lives in data/repos.
    if repo_path == "examples/sample_python_repo":
        fallback = Path("data/repos/sample_python_repo")
        if fallback.exists():
            return fallback

    return path


def build_indexed_repos(cases):
    cases_by_repo = defaultdict(list)

    for case in cases:
        cases_by_repo[case.repo_id].append(case)

    indexed_repos = {}

    for repo_id, repo_cases in cases_by_repo.items():
        repo_path = resolve_repo_path(repo_cases[0].repo_path)

        print("\n" + "=" * 100)
        print(f"Indexing repo: {repo_id}")
        print(f"Repo path: {repo_path}")

        indexed = build_codebase_agent(
            repo_path=repo_path,
            collection_name=f"eval_{repo_id}",
            reset_collection=True,
            use_llm=False,
            retrieval_mode=RETRIEVAL_MODE_FAST,
        )

        print(f"Python files:        {indexed.file_count}")
        print(f"Documentation files: {indexed.doc_count}")
        print(f"Ignored files:       {indexed.ignored_file_count}")
        print(f"Total chunks:        {indexed.chunk_count}")

        indexed_repos[repo_id] = indexed

    return indexed_repos


def print_result(result):
    status = (
        "PASS"
        if result.query_type_correct and result.expected_sources_all_found
        else "FAIL"
    )

    print("\n" + "-" * 100)
    print(f"{result.id} - {status}")
    print(f"Repo: {result.repo_id}")
    print(f"Question: {result.question}")

    print(f"\nExpected query type: {result.expected_query_type}")
    print(f"Actual query type:   {result.actual_query_type}")
    print(f"Query type correct:  {result.query_type_correct}")

    print("\nExpected sources:")
    for source in result.expected_sources:
        print(f"- {source}")

    print("\nActual sources:")
    if result.actual_sources:
        for source in result.actual_sources:
            print(f"- {source}")
    else:
        print("- No sources")

    print(f"\nSource hit count: {result.source_hit_count}/{len(result.expected_sources)}")
    print(f"Source recall:    {result.source_recall:.2f}")


def print_summary(title, results):
    summary = summarize_eval_results(results)

    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)
    print(f"Number of cases:                 {int(summary['num_cases'])}")
    print(f"Query type accuracy:             {summary['query_type_accuracy']:.2%}")
    print(f"Average source recall:           {summary['avg_source_recall']:.2%}")
    print(f"Expected sources all found rate: {summary['expected_sources_all_found_rate']:.2%}")


def main() -> None:
    eval_path = Path("data/eval_cases.json")

    cases = load_eval_cases(eval_path)
    print(f"Loaded {len(cases)} eval cases")

    indexed_repos = build_indexed_repos(cases)

    results = []

    for case in cases:
        indexed = indexed_repos[case.repo_id]

        response = indexed.agent.answer(case.question)
        result = evaluate_response(case, response)

        results.append(result)
        print_result(result)

    print_summary("Overall Evaluation Summary", results)

    repo_ids = sorted({result.repo_id for result in results})

    for repo_id in repo_ids:
        repo_results = [result for result in results if result.repo_id == repo_id]
        print_summary(f"Evaluation Summary - {repo_id}", repo_results)


if __name__ == "__main__":
    main()