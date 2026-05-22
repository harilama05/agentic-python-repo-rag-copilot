"""Evaluation runner for repository QA behavior."""

from collections import defaultdict
from pathlib import Path
import sys

from src.evaluation.eval_runner import (
    evaluate_response,
    load_eval_cases,
    summarize_eval_results,
)
from src.evaluation.metrics import (
    answer_non_empty,
    compute_latency_seconds,
    compute_source_precision,
    is_llm_failure,
    is_router_fallback,
    now_seconds,
    safe_average,
    validate_citations,
)
from src.indexing.codebase_indexer import build_codebase_agent
from src.core.settings import RETRIEVAL_MODE_FAST


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def resolve_repo_path(repo_path: str) -> Path:
    """Resolve repository paths used by eval cases."""
    path = Path(repo_path)

    if path.exists():
        return path

    if repo_path == "examples/sample_python_repo":
        fallback = Path("data/repos/sample_python_repo")
        if fallback.exists():
            return fallback

    return path


def build_indexed_repos(cases):
    """Index each repository referenced by eval cases once."""
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
            use_llm_router=True,
            save_metadata=False,
        )

        docs_text_count = indexed.doc_count + getattr(indexed, "text_count", 0)

        print(f"Python files:        {indexed.file_count}")
        print(f"Docs/Text files:     {docs_text_count}")
        print(f"JSON files:          {getattr(indexed, 'json_count', 0)}")
        print(f"Ignored files:       {indexed.ignored_file_count}")
        print(f"Total chunks:        {indexed.chunk_count}")

        indexed_repos[repo_id] = indexed

    return indexed_repos


def get_actual_response_sources(response):
    """Return raw response sources for extended metrics."""
    return getattr(response, "sources", []) or []


def get_expected_case_sources(case):
    """Return expected sources from an eval case."""
    return getattr(case, "expected_sources", []) or []


def print_result(result, extended_metrics):
    """Print one evaluation result in a human-readable format."""
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

    print("\nExtended metrics:")
    print(f"Source precision:  {extended_metrics['source_precision']:.2f}")
    print(f"Citation validity: {extended_metrics['citation_validity_rate']:.2f}")
    print(f"Latency seconds:   {extended_metrics['latency_seconds']:.2f}")
    print(f"Answer non-empty:  {extended_metrics['answer_non_empty']}")
    print(f"Router fallback:   {extended_metrics['router_fallback']}")
    print(f"LLM failure:       {extended_metrics['llm_failure']}")

    invalid_citations = extended_metrics.get("invalid_citations") or []

    if invalid_citations:
        print("\nInvalid citations:")
        for item in invalid_citations:
            print(f"- {item['reason']}: {item['source']}")


def print_summary(title, results, extended_results):
    """Print aggregate evaluation metrics."""
    summary = summarize_eval_results(results)

    latencies = [
        item["latency_seconds"]
        for item in extended_results
    ]

    source_precisions = [
        item["source_precision"]
        for item in extended_results
    ]

    citation_validities = [
        item["citation_validity_rate"]
        for item in extended_results
    ]

    answer_non_empty_values = [
        1.0 if item["answer_non_empty"] else 0.0
        for item in extended_results
    ]

    router_fallback_values = [
        1.0 if item["router_fallback"] else 0.0
        for item in extended_results
    ]

    llm_failure_values = [
        1.0 if item["llm_failure"] else 0.0
        for item in extended_results
    ]

    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)
    print(f"Number of cases:                 {int(summary['num_cases'])}")
    print(f"Query type accuracy:             {summary['query_type_accuracy']:.2%}")
    print(f"Average source recall:           {summary['avg_source_recall']:.2%}")
    print(f"Expected sources all found rate: {summary['expected_sources_all_found_rate']:.2%}")

    print("\nExtended Evaluation Summary")
    print("-" * 100)
    print(f"Average source precision:        {safe_average(source_precisions):.2%}")
    print(f"Average citation validity:       {safe_average(citation_validities):.2%}")
    print(f"Average latency seconds:         {safe_average(latencies):.2f}")
    print(f"Answer non-empty rate:           {safe_average(answer_non_empty_values):.2%}")
    print(f"Router fallback rate:            {safe_average(router_fallback_values):.2%}")
    print(f"LLM failure rate:                {safe_average(llm_failure_values):.2%}")


def main() -> None:
    """Run the repository QA evaluation suite."""
    eval_path = Path("data/eval_cases.json")

    cases = load_eval_cases(eval_path)
    print(f"Loaded {len(cases)} eval cases")

    indexed_repos = build_indexed_repos(cases)
    results = []
    extended_results = []

    for case in cases:
        indexed = indexed_repos[case.repo_id]

        start_time = now_seconds()
        response = indexed.agent.answer(case.question)
        end_time = now_seconds()

        result = evaluate_response(case, response)

        actual_sources = get_actual_response_sources(response)
        expected_sources = get_expected_case_sources(case)

        citation_metrics = validate_citations(
            repo_root=indexed.repo_path,
            sources=actual_sources,
        )

        raw_results = getattr(response, "raw_results", {}) or {}

        extended_metrics = {
            "id": result.id,
            "repo_id": result.repo_id,
            "latency_seconds": compute_latency_seconds(start_time, end_time),
            "source_precision": compute_source_precision(
                actual_sources=actual_sources,
                expected_sources=expected_sources,
            ),
            "citation_validity_rate": citation_metrics["citation_validity_rate"],
            "invalid_citations": citation_metrics["invalid_citations"],
            "answer_non_empty": answer_non_empty(getattr(response, "answer", "")),
            "router_fallback": is_router_fallback(raw_results),
            "llm_failure": is_llm_failure(raw_results),
        }

        results.append(result)
        extended_results.append(extended_metrics)

        print_result(result, extended_metrics)

    print_summary("Overall Evaluation Summary", results, extended_results)

    repo_ids = sorted({result.repo_id for result in results})

    for repo_id in repo_ids:
        repo_results = [
            result
            for result in results
            if result.repo_id == repo_id
        ]

        repo_extended_results = [
            item
            for item in extended_results
            if item["repo_id"] == repo_id
        ]

        print_summary(
            f"Evaluation Summary - {repo_id}",
            repo_results,
            repo_extended_results,
        )


if __name__ == "__main__":
    main()