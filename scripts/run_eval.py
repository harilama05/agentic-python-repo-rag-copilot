"""Run evaluation on an indexed codebase."""

import argparse
from src.indexing.repo_indexer import index_repository
from src.evaluation.testset_builder import build_testset
from src.evaluation.eval_runner import EvalRunner


def main():
    parser = argparse.ArgumentParser(description="Run RAG evaluation")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--num-cases", type=int, default=20)
    parser.add_argument("--output", default="data/eval/eval_results.json")
    args = parser.parse_args()

    print("Indexing repository...")
    indexed = index_repository(repo_path=args.repo, reset=True)

    print("Generating test cases...")
    cases = build_testset(indexed.metadata_store, num_cases=args.num_cases)

    print(f"Running {len(cases)} evaluation cases...")
    runner = EvalRunner(indexed.agent)
    results = runner.run_and_save(cases, args.output)

    # Print summary
    all_metrics = [r.metrics for r in results]
    if all_metrics:
        for key in all_metrics[0]:
            values = [m.get(key, 0) for m in all_metrics]
            avg = sum(values) / len(values)
            print(f"  {key}: {avg:.2%}")

    print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()
