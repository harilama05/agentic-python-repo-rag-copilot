from pathlib import Path

from src.evaluator import (
    evaluate_response,
    load_eval_cases,
    summarize_eval_results,
)
from src.indexer import build_codebase_agent


def main() -> None:
    repo_path = Path("examples/sample_python_repo")
    eval_path = Path("data/eval_cases.json")

    if not repo_path.exists():
        repo_path = Path("data/repos/sample_python_repo")

    print("Indexing repo for evaluation...")
    indexed = build_codebase_agent(
        repo_path=repo_path,
        collection_name="eval_sample_python_repo",
        reset_collection=True,
        use_llm=False,
    )

    print(f"Repo path: {indexed.repo_path}")
    print(f"Python files: {indexed.file_count}")
    print(f"Code chunks: {indexed.chunk_count}")

    cases = load_eval_cases(eval_path)
    print(f"\nLoaded {len(cases)} eval cases")

    results = []

    for case in cases:
        response = indexed.agent.answer(case.question)
        result = evaluate_response(case, response)
        results.append(result)

        status = "PASS" if result.query_type_correct and result.exact_source_match else "FAIL"

        print("\n" + "=" * 100)
        print(f"{case.id} - {status}")
        print(f"Question: {case.question}")
        print(f"Expected query type: {result.expected_query_type}")
        print(f"Actual query type:   {result.actual_query_type}")
        print(f"Query type correct:  {result.query_type_correct}")

        print("\nExpected sources:")
        for source in result.expected_sources:
            print(f"- {source}")

        print("\nActual sources:")
        for source in result.actual_sources:
            print(f"- {source}")

        print(f"\nSource recall: {result.source_recall:.2f}")

    summary = summarize_eval_results(results)

    print("\n" + "=" * 100)
    print("Evaluation Summary")
    print("=" * 100)
    print(f"Number of cases:          {int(summary['num_cases'])}")
    print(f"Query type accuracy:      {summary['query_type_accuracy']:.2%}")
    print(f"Average source recall:    {summary['avg_source_recall']:.2%}")
    print(f"Exact source match rate:  {summary['exact_source_match_rate']:.2%}")


if __name__ == "__main__":
    main()