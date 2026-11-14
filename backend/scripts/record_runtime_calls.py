"""Record a trusted local script/test run. This CLI executes code explicitly."""

import argparse
import json
import runpy
import sys
from pathlib import Path

from src.graph.runtime_trace import RuntimeCallRecorder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", default="manual run")
    parser.add_argument("--max-events", type=int, default=100000)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--script", type=Path)
    target.add_argument("--module")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    root = args.repo.resolve()
    if not root.is_dir():
        parser.error("--repo must be a directory")
    script = args.script.resolve() if args.script else None
    if script:
        try:
            script.relative_to(root)
        except ValueError:
            parser.error("--script must be inside --repo")
        if not script.is_file():
            parser.error("--script must be an existing file")
    if not 1 <= args.max_events <= 100000:
        parser.error("--max-events must be between 1 and 100000")
    if args.output.resolve().is_relative_to(root) and args.output.suffix == ".py":
        parser.error("Do not overwrite source files with trace output")
    recorder = RuntimeCallRecorder(root, label=args.label, max_events=args.max_events)
    previous_argv, previous_path = list(sys.argv), list(sys.path)
    try:
        sys.argv = [str(script) if script else args.module] + (args.args[1:] if args.args[:1] == ["--"] else args.args)
        # An earlier namespace package loses to any later regular package. Remove
        # the tooling root so backend/app cannot shadow a target repo's app/.
        tooling_root = Path(__file__).resolve().parents[1]
        if tooling_root != root:
            sys.path[:] = [item for item in sys.path if Path(item or Path.cwd()).resolve() != tooling_root]
        sys.path.insert(0, str(root))
        if script and script.parent != root:
            sys.path.insert(0, str(script.parent))
        with recorder:
            if script:
                runpy.run_path(str(script), run_name="__main__")
            else:
                runpy.run_module(args.module, run_name="__main__", alter_sys=True)
    finally:
        sys.argv[:], sys.path[:] = previous_argv, previous_path
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(recorder.report(), indent=2), encoding="utf-8")
        print(f"Runtime report written to {args.output}")


if __name__ == "__main__":
    main()
